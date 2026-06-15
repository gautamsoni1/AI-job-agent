from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from app.models.application import ApplicationStatus


class CreateApplicationRequest(BaseModel):
    job_id: str
    resume_id: Optional[str] = None
    cover_letter_id: Optional[str] = None
    notes: Optional[str] = None


class BulkApplicationRequest(BaseModel):
    job_ids: list[str]
    resume_id: Optional[str] = None


class UpdateStatusRequest(BaseModel):
    status: ApplicationStatus
    notes: Optional[str] = None
    interview_date: Optional[datetime] = None
    offer_amount: Optional[float] = None


class ApplicationResponse(BaseModel):
    id: str
    job_id: str
    resume_id: Optional[str]
    cover_letter_id: Optional[str]
    status: ApplicationStatus
    readiness_score: Optional[float]
    success_probability: Optional[float]
    interview_probability: Optional[float]
    applied_at: Optional[datetime]
    notes: Optional[str]
    interview_date: Optional[datetime]
    created_at: datetime


class ApplicationStatsResponse(BaseModel):
    total: int
    by_status: dict
    application_rate: float
    interview_rate: float
    offer_rate: float
    average_readiness_score: Optional[float]