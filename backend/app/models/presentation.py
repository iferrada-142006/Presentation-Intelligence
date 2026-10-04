from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Presentation(Base):
    __tablename__ = "presentations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    language = Column(String(10), default="es")
    status = Column(String(50), default="uploaded")
    # uploaded | processing | complete | failed
    duration_seconds = Column(Float, nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)

    video_file = relationship("VideoFile", back_populates="presentation", uselist=False)
    job = relationship("ProcessingJob", back_populates="presentation", uselist=False)
    transcript_segments = relationship("TranscriptSegment", back_populates="presentation")
    metrics = relationship("PresentationMetric", back_populates="presentation")


class VideoFile(Base):
    __tablename__ = "video_files"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    original_filename = Column(String(255), nullable=False)
    stored_filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    size_bytes = Column(Integer, nullable=True)
    format = Column(String(50), nullable=True)
    duration_seconds = Column(Float, nullable=True)
    fps = Column(Float, nullable=True)
    resolution = Column(String(20), nullable=True)
    audio_path = Column(String(500), nullable=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    presentation = relationship("Presentation", back_populates="video_file")


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    status = Column(String(50), default="queued")
    # queued | running | complete | failed
    current_stage = Column(String(50), nullable=True)
    # extract | speech | audio | video | analytics | rubric | feedback
    progress_pct = Column(Integer, default=0)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    presentation = relationship("Presentation", back_populates="job")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segments"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    start_seconds = Column(Float, nullable=False)
    end_seconds = Column(Float, nullable=False)
    text = Column(Text, nullable=False)
    word_count = Column(Integer, default=0)
    confidence = Column(Float, nullable=True)
    # [{word, start, end, probability}]
    words_json = Column(JSON, nullable=True)

    presentation = relationship("Presentation", back_populates="transcript_segments")


class PresentationMetric(Base):
    __tablename__ = "presentation_metrics"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    metric_name = Column(String(100), nullable=False)
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)
    # 0.0–1.0: how reliable is this measurement
    confidence = Column(Float, default=1.0)
    computed_at = Column(DateTime(timezone=True), server_default=func.now())

    presentation = relationship("Presentation", back_populates="metrics")
