import logging
from datetime import datetime, timezone
from faster_whisper import WhisperModel
from sqlalchemy.orm import Session
from app.models import (
    Presentation, VideoFile, ProcessingJob,
    TranscriptSegment, PresentationMetric,
)
from app.services.extraction.ffmpeg import get_video_metadata, extract_audio
from app.services.speech.transcriber import transcribe
from app.services.speech.filler_words import detect_fillers, compute_filler_metrics
from app.config import settings

logger = logging.getLogger(__name__)


def _set_stage(job: ProcessingJob, stage: str, pct: int, db: Session):
    job.current_stage = stage
    job.progress_pct = pct
    db.commit()
    logger.info(f"[job {job.id}] stage={stage} progress={pct}%")


def _save_metric(presentation_id: int, name: str, value: float,
                 unit: str, confidence: float, db: Session):
    db.add(PresentationMetric(
        presentation_id=presentation_id,
        metric_name=name,
        value=value,
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

        # ── Stage 1: EXTRACT ────────────────────────────────────────────────
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

        # ── Stage 2: SPEECH ─────────────────────────────────────────────────
        _set_stage(job, "speech", 20, db)
        result = transcribe(audio_path, whisper_model, language=presentation.language)

        # Persist transcript segments
        total_words = 0
        for seg in result["segments"]:
            word_count = len(seg["words"]) if seg["words"] else len(seg["text"].split())
            total_words += word_count
            # avg_logprob is a proxy for confidence; convert to 0-1 range (logprob ∈ [-∞, 0])
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

        _set_stage(job, "speech", 55, db)

        # ── Filler word detection ────────────────────────────────────────────
        filler_occurrences = detect_fillers(result["segments"], result["language"])
        filler_metrics = compute_filler_metrics(
            filler_occurrences,
            total_words,
            result["duration_seconds"],
        )
        logger.info(
            f"[job {job_id}] words={total_words} fillers={filler_metrics['filler_count']}"
        )

        # ── Persist speech metrics ───────────────────────────────────────────
        duration = presentation.duration_seconds or result["duration_seconds"]
        avg_wpm = round((total_words / duration) * 60, 1) if duration > 0 else 0.0

        metrics = [
            ("total_words",         total_words,                        "words",        1.0),
            ("avg_wpm",             avg_wpm,                            "wpm",          0.9),
            ("filler_count",        filler_metrics["filler_count"],     "count",        0.7),
            ("filler_rate_per_min", filler_metrics["filler_rate_per_minute"], "count/min", 0.7),
            ("detected_language_prob", result["language_probability"],  "probability",  1.0),
        ]
        for name, value, unit, conf in metrics:
            _save_metric(presentation.id, name, float(value), unit, conf, db)

        _set_stage(job, "speech", 70, db)

        # Stages 3-6 (audio analysis, video CV, analytics, feedback) → future phases
        # Progress jumps to complete for now
        job.status = "complete"
        job.current_stage = None
        job.progress_pct = 100
        job.completed_at = datetime.now(timezone.utc)
        presentation.status = "complete"
        presentation.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(f"[job {job_id}] complete — {total_words} words, {avg_wpm} WPM")

    except Exception as e:
        logger.exception(f"[job {job_id}] failed: {e}")
        job.status = "failed"
        job.error_message = str(e)
        presentation.status = "failed"
        db.commit()
