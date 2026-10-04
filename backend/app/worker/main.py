"""
Worker process: polls processing_jobs and runs the pipeline.
The Whisper model is loaded once at startup and reused across jobs.
"""
import time
import logging
from app.database import SessionLocal
from app.models import ProcessingJob
from app.services.speech.transcriber import load_model
from app.worker import pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 5


def main():
    logger.info("Loading Whisper model at startup...")
    whisper_model = load_model()
    logger.info("Worker ready — polling every %ds", POLL_INTERVAL)

    while True:
        db = SessionLocal()
        try:
            job = (
                db.query(ProcessingJob)
                .filter(ProcessingJob.status == "queued")
                .order_by(ProcessingJob.created_at.asc())
                .with_for_update(skip_locked=True)
                .first()
            )
            if job:
                logger.info(f"Picked up job {job.id} (presentation {job.presentation_id})")
                pipeline.run(job.id, db, whisper_model)
            else:
                time.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            time.sleep(POLL_INTERVAL)
        finally:
            db.close()


if __name__ == "__main__":
    main()
