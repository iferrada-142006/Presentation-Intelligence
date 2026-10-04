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
    audio_features = relationship("AudioFeature", back_populates="presentation")
    video_features = relationship("VideoFeature", back_populates="presentation")
    timeline_events = relationship("TimelineEvent", back_populates="presentation")
    rubric_scores = relationship("RubricScore", back_populates="presentation")
    feedback_items = relationship("FeedbackItem", back_populates="presentation")


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


class AudioFeature(Base):
    __tablename__ = "audio_features"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    # Center of the analysis window
    timestamp_seconds = Column(Float, nullable=False)
    window_seconds = Column(Float, nullable=False, default=0.5)
    # Volume — RMS energy of this window (relative, not dB)
    energy_rms = Column(Float, nullable=True)
    # True if energy < silence threshold for this presentation
    is_silence = Column(Integer, nullable=True)  # 0/1 (bool-compatible)
    # Words/min in this window derived from transcript timestamps
    local_wpm = Column(Float, nullable=True)

    presentation = relationship("Presentation", back_populates="audio_features")


class VideoFeature(Base):
    __tablename__ = "video_features"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    timestamp_seconds = Column(Float, nullable=False)
    frame_number = Column(Integer, nullable=True)
    # Face detection (0/1)
    face_detected = Column(Integer, nullable=True)
    # Head orientation (degrees) via PnP from face landmarks
    head_yaw = Column(Float, nullable=True)    # + = turned right
    head_pitch = Column(Float, nullable=True)  # + = tilted down
    head_roll = Column(Float, nullable=True)   # + = rolled right
    # Body movement: mean landmark displacement (normalized 0–1) vs. prev frame
    body_movement = Column(Float, nullable=True)

    presentation = relationship("Presentation", back_populates="video_features")


class RubricScore(Base):
    __tablename__ = "rubric_scores"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    dimension = Column(String(50), nullable=False)
    # verbal_rhythm | filler_density | silence_management | vocal_dynamics | visual_presence
    score = Column(Float, nullable=False)           # 0–100
    level = Column(Integer, nullable=False)         # 0–4
    level_label = Column(String(50), nullable=False)
    primary_metric = Column(String(100), nullable=True)
    primary_value = Column(Float, nullable=True)
    evidence = Column(Text, nullable=True)          # human-readable explanation
    rubric_version = Column(String(20), default="v1.0")

    presentation = relationship("Presentation", back_populates="rubric_scores")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    layer = Column(String(20), nullable=False)   # audio | speech | vision
    event_type = Column(String(50), nullable=False)
    # pause | wpm_sprint | filler_cluster | head_away | face_absent | movement_spike
    start_seconds = Column(Float, nullable=False)
    end_seconds = Column(Float, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    magnitude = Column(Float, nullable=True)     # severity value (wpm, seconds, count…)
    description = Column(Text, nullable=True)    # human-readable for LLM and UI

    presentation = relationship("Presentation", back_populates="timeline_events")


class FeedbackItem(Base):
    __tablename__ = "feedback_items"

    id = Column(Integer, primary_key=True, index=True)
    presentation_id = Column(Integer, ForeignKey("presentations.id"), nullable=False)
    category = Column(String(50), nullable=False)  # strength | improvement | exercise
    content = Column(Text, nullable=False)
    evidence = Column(Text, nullable=True)          # metric or quote that grounds this
    timestamp_ref = Column(Float, nullable=True)    # optional second reference
    llm_model = Column(String(100), nullable=True)
    llm_prompt_version = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    presentation = relationship("Presentation", back_populates="feedback_items")
