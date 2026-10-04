"""
Worker process: polls processing_jobs table and runs the pipeline.
One job at a time (MAX_CONCURRENT_JOBS=1).
"""
import time
import logging
from app.database import SessionLocal
from app.models import ProcessingJob
from app.worker import pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds


def main():
    logger.info("Worker started — polling every %ds", POLL_INTERVAL)
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
                pipeline.run(job.id, db)
            else:
                time.sleep(POLL_INTERVAL)
        except Exception as e:
            logger.exception(f"Worker loop error: {e}")
            time.sleep(POLL_INTERVAL)
        finally:
            db.close()


if __name__ == "__main__":
    main()
