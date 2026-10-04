from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class JobStatus(BaseModel):
    id: int
    status: str
    current_stage: Optional[str]
    progress_pct: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PresentationStatus(BaseModel):
    id: int
    title: str
    status: str
    duration_seconds: Optional[float]
    uploaded_at: datetime
    processed_at: Optional[datetime]
    job: Optional[JobStatus]

    model_config = {"from_attributes": True}


class PresentationCreate(BaseModel):
    id: int
    title: str
    status: str
    uploaded_at: datetime
    job_id: int

    model_config = {"from_attributes": True}


class PresentationListItem(BaseModel):
    id: int
    title: str
    status: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None
    avg_score: Optional[float] = None
    avg_wpm: Optional[float] = None
    filler_count: Optional[float] = None
