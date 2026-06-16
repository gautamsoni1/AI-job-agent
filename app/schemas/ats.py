from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ATSScoreRequest(BaseModel):
    resume_id: str
    job_description: str
    job_id: Optional[str] = None


class ATSScoreResponse(BaseModel):
    report_id: str
    ats_score: float
    keyword_coverage: dict
    missing_keywords: list[str]
    section_analysis: dict
    formatting_issues: list[str]
    predicted_pass_rate: float
    improvement_plan: list[dict]
    skill_relevance: Optional[float]
    industry_alignment: Optional[float]


class ATSTrendItem(BaseModel):
    report_id: str
    ats_score: float
    job_description_snippet: Optional[str]
    created_at: datetime


class ATSTrendResponse(BaseModel):
    trend: list[ATSTrendItem]
    first_score: Optional[float]
    latest_score: Optional[float]
    improvement: Optional[float]