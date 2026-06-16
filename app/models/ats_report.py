from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class ATSReportDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str
    resume_id: str
    job_id: Optional[str] = None
    job_description_snippet: Optional[str] = None
    ats_score: float
    keyword_coverage: dict = {}
    missing_keywords: list[str] = []
    section_analysis: dict = {}
    formatting_issues: list[str] = []
    skill_relevance: Optional[float] = None
    industry_alignment: Optional[float] = None
    improvement_plan: list[dict] = []
    predicted_pass_rate: float = 0.0
    full_report: dict = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True