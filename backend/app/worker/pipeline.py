import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import Presentation, VideoFile, ProcessingJob
from app.services.extraction.ffmpeg import get_video_metadata, extract_audio
from app.config import settings

logger = logging.getLogger(__name__)


def _set_stage(job: ProcessingJob, stage: str, pct: int, db: Session):
    job.current_stage = stage
    job.progress_pct = pct
    db.commit()
    logger.info(f"[job {job.id}] stage={stage} progress={pct}%")


def run(job_id: int, db: Session):
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

        # Stage 1 — Extract metadata + audio
        _set_stage(job, "extract", 10, db)
        metadata = get_video_metadata(video_file.file_path)

        video_file.duration_seconds = metadata["duration_seconds"]
        video_file.fps = metadata["fps"]
        video_file.resolution = metadata["resolution"]
        presentation.duration_seconds = metadata["duration_seconds"]
        db.commit()
        logger.info(
            f"[job {job_id}] metadata: {metadata['duration_seconds']:.1f}s "
            f"{metadata['resolution']} @ {metadata['fps']}fps"
        )

        _set_stage(job, "extract", 30, db)
        audio_path = extract_audio(video_file.file_path, settings.upload_dir)
        video_file.audio_path = audio_path
        db.commit()
        logger.info(f"[job {job_id}] audio extracted → {audio_path}")

        # Stages 2-6 will be implemented in future phases
        # speech, audio_analysis, video_analysis, analytics, feedback
        _set_stage(job, "extract", 100, db)

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
