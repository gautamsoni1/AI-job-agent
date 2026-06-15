from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class TimelineEventType(str, Enum):
    RESUME_UPLOADED = "RESUME_UPLOADED"
    RESUME_ANALYZED = "RESUME_ANALYZED"
    RESUME_REWRITTEN = "RESUME_REWRITTEN"
    ATS_SCORED = "ATS_SCORED"
    ATS_IMPROVED = "ATS_IMPROVED"
    JOB_DISCOVERED = "JOB_DISCOVERED"
    JOB_SCOUTED = "JOB_SCOUTED"
    JOB_MATCHED = "JOB_MATCHED"
    JOB_SAVED = "JOB_SAVED"
    COVER_LETTER_GENERATED = "COVER_LETTER_GENERATED"
    APPLICATION_PREPARED = "APPLICATION_PREPARED"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    APPLICATION_STATUS_CHANGED = "APPLICATION_STATUS_CHANGED"
    INTERVIEW_PREP_GENERATED = "INTERVIEW_PREP_GENERATED"
    INTERVIEW_ANSWER_EVALUATED = "INTERVIEW_ANSWER_EVALUATED"
    CAREER_ROADMAP_GENERATED = "CAREER_ROADMAP_GENERATED"
    SKILL_RECOMMENDED = "SKILL_RECOMMENDED"
    MARKET_ANALYSIS_RUN = "MARKET_ANALYSIS_RUN"
    CAREER_HEALTH_CALCULATED = "CAREER_HEALTH_CALCULATED"


class AITimelineEventDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str
    event_type: TimelineEventType
    agent_name: Optional[str] = None
    task: Optional[str] = None
    title: str
    description: str
    metadata: dict = {}
    result_ref: Optional[str] = None  # reference ID to the result document
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True