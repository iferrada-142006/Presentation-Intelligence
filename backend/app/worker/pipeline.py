import logging
from datetime import datetime, timezone
from faster_whisper import WhisperModel
from sqlalchemy.orm import Session
from app.models import (
    Presentation, VideoFile, ProcessingJob,
    TranscriptSegment, PresentationMetric, AudioFeature, FeedbackItem,
)
from app.services.extraction.ffmpeg import get_video_metadata, extract_audio
from app.services.speech.transcriber import transcribe
from app.services.speech.filler_words import detect_fillers, compute_filler_metrics
from app.services.audio.analyzer import analyze as analyze_audio, compute_audio_metrics
from app.config import settings
from app.services.feedback.llm import generate as generate_feedback

logger = logging.getLogger(__name__)

STAGES = {
    "extract":  (5,  20),
    "speech":   (20, 55),
    "audio":    (55, 80),
    # video, analytics, rubric, feedback → future phases
}


def _set_stage(job: ProcessingJob, stage: str, pct: int, db: Session):
    job.current_stage = stage
    job.progress_pct = pct
    db.commit()
    logger.info(f"[job {job.id}] stage={stage} {pct}%")


def _save_metric(presentation_id: int, name: str, value: float,
                 unit: str, confidence: float, db: Session):
    db.add(PresentationMetric(
        presentation_id=presentation_id,
        metric_name=name,
        value=round(float(value), 6),
        unit=unit,
        confidence=confidence,
    ))


def run(job_id: int, db: Session, whisper_model: WhisperModel):
    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        logger.error(f"Job {job_id} not found")
        return

    presentation = db.query(Presentation).filter(
        Presentation.id == job.presentation_id
    ).first()
    video_file = db.query(VideoFile).filter(
        VideoFile.presentation_id == job.presentation_id
    ).first()

    try:
        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        presentation.status = "processing"
        db.commit()

        # ── Stage 1: EXTRACT ─────────────────────────────────────────────────
        _set_stage(job, "extract", 5, db)
        metadata = get_video_metadata(video_file.file_path)
        video_file.duration_seconds = metadata["duration_seconds"]
        video_file.fps = metadata["fps"]
        video_file.resolution = metadata["resolution"]
        presentation.duration_seconds = metadata["duration_seconds"]
        db.commit()

        _set_stage(job, "extract", 15, db)
        audio_path = extract_audio(video_file.file_path, settings.upload_dir)
        video_file.audio_path = audio_path
        db.commit()
        logger.info(f"[job {job_id}] audio → {audio_path}")

        # ── Stage 2: SPEECH ──────────────────────────────────────────────────
        _set_stage(job, "speech", 20, db)
        speech_result = transcribe(audio_path, whisper_model, language=presentation.language)

        total_words = 0
        for seg in speech_result["segments"]:
            word_count = len(seg["words"]) if seg["words"] else len(seg["text"].split())
            total_words += word_count
            confidence = max(0.0, min(1.0, 1.0 + seg.get("avg_logprob", -0.5)))
            db.add(TranscriptSegment(
                presentation_id=presentation.id,
                start_seconds=seg["start"],
                end_seconds=seg["end"],
                text=seg["text"],
                word_count=word_count,
                confidence=round(confidence, 3),
                words_json=seg["words"],
            ))

        _set_stage(job, "speech", 45, db)

        filler_occurrences = detect_fillers(speech_result["segments"], speech_result["language"])
        filler_metrics = compute_filler_metrics(
            filler_occurrences,
            total_words,
            speech_result["duration_seconds"],
        )

        duration = presentation.duration_seconds or speech_result["duration_seconds"]
        avg_wpm = round((total_words / duration) * 60, 1) if duration > 0 else 0.0

        for name, value, unit, conf in [
            ("total_words",          total_words,                              "words",      1.0),
            ("avg_wpm",              avg_wpm,                                  "wpm",        0.9),
            ("filler_count",         filler_metrics["filler_count"],           "count",      0.7),
            ("filler_rate_per_min",  filler_metrics["filler_rate_per_minute"], "count/min",  0.7),
            ("detected_language_prob", speech_result["language_probability"],  "probability",1.0),
        ]:
            _save_metric(presentation.id, name, float(value), unit, conf, db)

        _set_stage(job, "speech", 55, db)
        logger.info(f"[job {job_id}] speech done — {total_words} words, {avg_wpm} WPM, "
                    f"{filler_metrics['filler_count']} fillers")

        # ── Stage 3: AUDIO ANALYSIS ──────────────────────────────────────────
        _set_stage(job, "audio", 58, db)

        # Pass transcript word data so audio stage can compute local WPM per frame
        segments_for_audio = [
            {"words": seg["words"]} for seg in speech_result["segments"]
        ]
        audio_result = analyze_audio(audio_path, segments_for_audio)

        # Bulk-insert audio features (one row per frame)
        db.bulk_insert_mappings(AudioFeature, [
            {
                "presentation_id": presentation.id,
                "timestamp_seconds": t,
                "window_seconds": 0.5,
                "energy_rms": round(float(rms), 6),
                "is_silence": sil,
                "local_wpm": round(float(wpm), 2),
            }
            for t, rms, sil, wpm in zip(
                audio_result.frame_times,
                audio_result.frame_rms,
                audio_result.frame_is_silence,
                audio_result.frame_local_wpm,
            )
        ])

        _set_stage(job, "audio", 72, db)

        for name, value, unit, conf in compute_audio_metrics(audio_result):
            _save_metric(presentation.id, name, float(value), unit, conf, db)

        logger.info(
            f"[job {job_id}] audio done — {len(audio_result.pauses)} pauses, "
            f"silence ratio={audio_result.silence_duration_seconds/audio_result.total_duration_seconds:.1%}"
        )

        # ── Stage 4: LLM FEEDBACK ────────────────────────────────────────────
        _set_stage(job, "feedback", 80, db)

        # Rebuild metric dict from what was just written to DB
        metric_rows = db.query(PresentationMetric).filter(
            PresentationMetric.presentation_id == presentation.id
        ).all()
        metrics_for_llm = {m.metric_name: m.value for m in metric_rows}

        # Build transcript text (first 4000 chars to stay within token budget)
        transcript_rows = db.query(TranscriptSegment).filter(
            TranscriptSegment.presentation_id == presentation.id
        ).order_by(TranscriptSegment.start_seconds).all()
        transcript_text = " ".join(r.text.strip() for r in transcript_rows)[:4000]

        presentation_data = {
            "presentation": {
                "duration_seconds": presentation.duration_seconds,
            },
            "metrics": metrics_for_llm,
            "transcript_text": transcript_text,
        }

        feedback_items = generate_feedback(presentation_data, language=presentation.language)
        for item in feedback_items:
            db.add(FeedbackItem(
                presentation_id=presentation.id,
                category=item["category"],
                content=item["content"],
                evidence=item.get("evidence"),
                llm_model=item.get("llm_model"),
                llm_prompt_version=item.get("llm_prompt_version"),
            ))
        db.commit()

        logger.info(f"[job {job_id}] feedback done — {len(feedback_items)} items")
        _set_stage(job, "feedback", 95, db)

        # ── Complete ─────────────────────────────────────────────────────────
        job.status = "complete"
        job.current_stage = None
        job.progress_pct = 100
        job.completed_at = datetime.now(timezone.utc)
        presentation.status = "complete"
        presentation.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"[job {job_id}] complete")

    except Exception as e:
        logger.exception(f"[job {job_id}] failed: {e}")
        job.status = "failed"
        job.error_message = str(e)
        presentation.status = "failed"
        db.commit()
