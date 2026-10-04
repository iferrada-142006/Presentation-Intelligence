from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal


class TranscriptSegmentOut(BaseModel):
    start_seconds: float
    end_seconds: float
    text: str
    word_count: int
    confidence: Optional[float]
    model_config = {"from_attributes": True}


class MetricsOut(BaseModel):
    # Speech / audio
    total_words: Optional[float] = None
    avg_wpm: Optional[float] = None
    filler_count: Optional[float] = None
    filler_rate_per_min: Optional[float] = None
    pause_count: Optional[float] = None
    avg_pause_duration: Optional[float] = None
    max_pause_duration: Optional[float] = None
    pause_rate_per_min: Optional[float] = None
    silence_ratio: Optional[float] = None
    energy_cv: Optional[float] = None
    wpm_std: Optional[float] = None
    detected_language_prob: Optional[float] = None
    # Vision (Phase 5+)
    face_visible_ratio: Optional[float] = None
    head_yaw_mean: Optional[float] = None
    head_yaw_std: Optional[float] = None
    head_pitch_mean: Optional[float] = None
    head_pitch_std: Optional[float] = None
    head_forward_ratio: Optional[float] = None
    body_movement_mean: Optional[float] = None
    body_movement_std: Optional[float] = None
    # Iris gaze
    gaze_offset_mean: Optional[float] = None
    gaze_offset_std: Optional[float] = None
    gaze_centred_ratio: Optional[float] = None
    # Hands
    hand_visible_ratio: Optional[float] = None
    hand_movement_mean: Optional[float] = None
    hand_movement_std: Optional[float] = None


class RubricScoreOut(BaseModel):
    dimension: str
    score: float
    level: int
    level_label: str
    primary_metric: Optional[str]
    primary_value: Optional[float]
    evidence: Optional[str]
    model_config = {"from_attributes": True}


class TimelineEventOut(BaseModel):
    layer: str
    event_type: str
    start_seconds: float
    end_seconds: Optional[float]
    duration_seconds: Optional[float]
    magnitude: Optional[float]
    description: Optional[str]
    model_config = {"from_attributes": True}


class FeedbackItemOut(BaseModel):
    category: str
    content: str
    evidence: Optional[str]
    model_config = {"from_attributes": True}


class ReportOut(BaseModel):
    id: int
    title: str
    language: str
    status: str
    duration_seconds: Optional[float]
    uploaded_at: datetime
    processed_at: Optional[datetime]
    metrics: MetricsOut
    rubric: list[RubricScoreOut]
    transcript: list[TranscriptSegmentOut]
    timeline: list[TimelineEventOut]
    feedback: list[FeedbackItemOut]
    model_config = {"from_attributes": True}
