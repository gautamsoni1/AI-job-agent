from pydantic import BaseModel
from typing import Optional


class CareerRoadmapResponse(BaseModel):
    short_term_goals: list[dict]  # 0-3 months
    mid_term_goals: list[dict]   # 3-12 months
    long_term_goals: list[dict]  # 1-3 years
    recommended_skills: list[str]
    recommended_certifications: list[dict]
    recommended_projects: list[dict]
    summary: str


class CareerGapAnalysisResponse(BaseModel):
    target_role: str
    current_level: str
    target_level: str
    skill_gaps: list[dict]
    experience_gaps: list[dict]
    education_gaps: list[dict]
    time_to_ready: str
    action_plan: list[dict]


class WeeklyGoalResponse(BaseModel):
    week_focus: str
    goals: list[dict]
    daily_tasks: list[dict]
    skill_to_practice: str
    job_to_apply_count: int
    networking_goal: str


class CareerHealthResponse(BaseModel):
    overall_score: float
    resume_strength: float
    skill_market_fit: float
    application_momentum: float
    interview_readiness: float
    network_strength: float
    recommendations: list[str]