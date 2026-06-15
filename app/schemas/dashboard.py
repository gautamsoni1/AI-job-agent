from pydantic import BaseModel
from typing import Optional


class DashboardScores(BaseModel):
    career_health_score: float
    resume_strength_score: float
    application_success_rate: float
    ats_improvement_trend: float
    interview_conversion_rate: float
    market_readiness_score: float
    job_search_progress_score: float
    top_missing_skills: list[str]
    weekly_application_goal: int
    applications_this_week: int


class DashboardResponse(BaseModel):
    scores: DashboardScores
    recent_applications: list[dict]
    top_opportunities: list[dict]
    recent_timeline: list[dict]
    ats_trend: list[dict]
    notifications: list[dict]