import os
import re
import uuid
import aiofiles
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from sqlalchemy.orm import joinedload
from app.models import Presentation, VideoFile, ProcessingJob, TranscriptSegment, PresentationMetric, AudioFeature, VideoFeature, RubricScore, TimelineEvent, FeedbackItem
from app.schemas.presentation import PresentationCreate, PresentationStatus
from app.schemas.report import ReportOut, MetricsOut, RubricScoreOut, TranscriptSegmentOut, TimelineEventOut, FeedbackItemOut
from app.config import settings

_VIDEO_CONTENT_TYPES = {
    ".mp4": "video/mp4",
    ".webm": "video/webm",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".mkv": "video/x-matroska",
}

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

    # Rubric scores
    rubric_rows = db.query(RubricScore).filter(
        RubricScore.presentation_id == presentation_id
    ).all()
    rubric = [RubricScoreOut.model_validate(r) for r in rubric_rows]

    # Timeline events ordered by start time
    event_rows = db.query(TimelineEvent).filter(
        TimelineEvent.presentation_id == presentation_id
    ).order_by(TimelineEvent.start_seconds).all()
    timeline = [TimelineEventOut.model_validate(e) for e in event_rows]

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
        rubric=rubric,
        transcript=transcript,
        timeline=timeline,
        feedback=feedback,
    )


@router.get("/{presentation_id}/video")
def stream_video(
    presentation_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    video = db.query(VideoFile).filter(
        VideoFile.presentation_id == presentation_id
    ).first()
    if not video:
        raise HTTPException(status_code=404, detail="Video no encontrado")
    if not os.path.exists(video.file_path):
        raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")

    file_size = os.path.getsize(video.file_path)
    ext = os.path.splitext(video.file_path)[1].lower()
    content_type = _VIDEO_CONTENT_TYPES.get(ext, "video/mp4")

    def _iter(start: int, end: int):
        with open(video.file_path, "rb") as f:
            f.seek(start)
            remaining = end - start + 1
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    range_header = request.headers.get("Range")
    if range_header:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header)
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else file_size - 1
            end = min(end, file_size - 1)
            return StreamingResponse(
                _iter(start, end),
                status_code=206,
                media_type=content_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(end - start + 1),
                },
            )

    return StreamingResponse(
        _iter(0, file_size - 1),
        media_type=content_type,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
        },
    )


@router.get("/{presentation_id}/chart-data")
def get_chart_data(presentation_id: int, db: Session = Depends(get_db)):
    presentation = db.query(Presentation).filter(
        Presentation.id == presentation_id
    ).first()
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentación no encontrada")

    audio_rows = (
        db.query(AudioFeature)
        .filter(AudioFeature.presentation_id == presentation_id)
        .order_by(AudioFeature.timestamp_seconds)
        .all()
    )
    video_rows = (
        db.query(VideoFeature)
        .filter(VideoFeature.presentation_id == presentation_id)
        .order_by(VideoFeature.timestamp_seconds)
        .all()
    )

    return {
        "duration_seconds": presentation.duration_seconds,
        "audio": [
            {
                "t": r.timestamp_seconds,
                "rms": round(r.energy_rms, 4) if r.energy_rms is not None else None,
                "wpm": round(r.local_wpm, 1) if r.local_wpm is not None else None,
                "silence": bool(r.is_silence),
            }
            for r in audio_rows
        ],
        "video": [
            {
                "t": r.timestamp_seconds,
                "yaw": round(r.head_yaw, 1) if r.head_yaw is not None else None,
                "face": bool(r.face_detected),
            }
            for r in video_rows
        ],
    }
