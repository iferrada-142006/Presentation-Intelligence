import os
import uuid
import aiofiles
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from sqlalchemy.orm import joinedload
from app.models import Presentation, VideoFile, ProcessingJob, TranscriptSegment, PresentationMetric, FeedbackItem
from app.schemas.presentation import PresentationCreate, PresentationStatus
from app.schemas.report import ReportOut, MetricsOut, TranscriptSegmentOut, FeedbackItemOut
from app.config import settings

router = APIRouter(prefix="/api/presentations", tags=["presentations"])

ALLOWED_EXTENSIONS = {".mp4", ".webm", ".mov", ".avi", ".mkv"}
MAX_SIZE_BYTES = settings.max_video_size_mb * 1024 * 1024


@router.post("/", response_model=PresentationCreate, status_code=201)
async def upload_presentation(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    language: str = Form(default="es"),
    db: Session = Depends(get_db),
):
    # Validate extension
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Formato no soportado: {ext}. Usa: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    # Save file to disk
    stored_filename = f"{uuid.uuid4()}{ext}"
    file_path = os.path.join(settings.upload_dir, stored_filename)

    size_bytes = 0
    async with aiofiles.open(file_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            size_bytes += len(chunk)
            if size_bytes > MAX_SIZE_BYTES:
                await f.close()
                os.unlink(file_path)
                raise HTTPException(
                    status_code=413,
                    detail=f"El archivo supera el límite de {settings.max_video_size_mb} MB",
                )
            await f.write(chunk)

    presentation_title = title.strip() or (file.filename or "Sin título")

    # Create DB records
    presentation = Presentation(title=presentation_title, language=language)
    db.add(presentation)
    db.flush()

    video_file = VideoFile(
        presentation_id=presentation.id,
        original_filename=file.filename or stored_filename,
        stored_filename=stored_filename,
        file_path=file_path,
        size_bytes=size_bytes,
        format=ext.lstrip("."),
    )
    db.add(video_file)

    job = ProcessingJob(presentation_id=presentation.id, status="queued")
    db.add(job)
    db.commit()
    db.refresh(presentation)
    db.refresh(job)

    return PresentationCreate(
        id=presentation.id,
        title=presentation.title,
        status=presentation.status,
        uploaded_at=presentation.uploaded_at,
        job_id=job.id,
    )


@router.get("/{presentation_id}/status", response_model=PresentationStatus)
def get_status(presentation_id: int, db: Session = Depends(get_db)):
    presentation = (
        db.query(Presentation)
        .options(joinedload(Presentation.job))
        .filter(Presentation.id == presentation_id)
        .first()
    )
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentación no encontrada")
    return presentation


@router.get("/", response_model=list[PresentationStatus])
def list_presentations(db: Session = Depends(get_db)):
    return db.query(Presentation).order_by(Presentation.uploaded_at.desc()).all()


@router.get("/{presentation_id}/report", response_model=ReportOut)
def get_report(presentation_id: int, db: Session = Depends(get_db)):
    presentation = db.query(Presentation).filter(
        Presentation.id == presentation_id
    ).first()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentación no encontrada")
    if presentation.status not in ("complete",):
        raise HTTPException(
            status_code=409,
            detail=f"Reporte no disponible aún — estado actual: {presentation.status}",
        )

    # Pivot presentation_metrics rows → flat dict
    raw_metrics = db.query(PresentationMetric).filter(
        PresentationMetric.presentation_id == presentation_id
    ).all()
    metrics_dict = {m.metric_name: m.value for m in raw_metrics}
    metrics = MetricsOut(**{k: metrics_dict.get(k) for k in MetricsOut.model_fields})

    # Transcript segments ordered by start time
    segments = db.query(TranscriptSegment).filter(
        TranscriptSegment.presentation_id == presentation_id
    ).order_by(TranscriptSegment.start_seconds).all()
    transcript = [TranscriptSegmentOut.model_validate(s) for s in segments]

    # Feedback items
    feedback_rows = db.query(FeedbackItem).filter(
        FeedbackItem.presentation_id == presentation_id
    ).order_by(FeedbackItem.id).all()
    feedback = [FeedbackItemOut.model_validate(f) for f in feedback_rows]

    return ReportOut(
        id=presentation.id,
        title=presentation.title,
        language=presentation.language,
        status=presentation.status,
        duration_seconds=presentation.duration_seconds,
        uploaded_at=presentation.uploaded_at,
        processed_at=presentation.processed_at,
        metrics=metrics,
        transcript=transcript,
        feedback=feedback,
    )
