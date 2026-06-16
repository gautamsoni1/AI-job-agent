from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class ApplicationStatus(str, Enum):
    PLANNED = "PLANNED"
    APPLIED = "APPLIED"
    SCREENING = "SCREENING"
    INTERVIEW = "INTERVIEW"
    TECHNICAL = "TECHNICAL"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    GHOSTED = "GHOSTED"


class ApplicationDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str
    job_id: str
    resume_id: Optional[str] = None
    cover_letter_id: Optional[str] = None
    status: ApplicationStatus = ApplicationStatus.PLANNED
    readiness_score: Optional[float] = None
    success_probability: Optional[float] = None
    interview_probability: Optional[float] = None
    applied_at: Optional[datetime] = None
    notes: Optional[str] = None
    interview_date: Optional[datetime] = None
    offer_amount: Optional[float] = None
    offer_currency: str = "USD"
    status_history: list[dict] = []
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True