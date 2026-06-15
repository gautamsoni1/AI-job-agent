from pydantic import BaseModel
from typing import Optional


class MatchRequest(BaseModel):
    resume_id: str
    job_id: str


class GapItem(BaseModel):
    skill: str
    importance: str  # HIGH | MEDIUM | LOW
    how_to_fill: str
    time_estimate: str


class MatchResponse(BaseModel):
    match_id: str
    overall_match: float
    skill_match: float
    experience_match: float
    keyword_match: float
    education_match: float
    gap_analysis: list[GapItem]
    match_explanation: str
    recommendation: str