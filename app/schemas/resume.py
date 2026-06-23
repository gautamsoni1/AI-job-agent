from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class ResumeUploadResponse(BaseModel):
    id: str
    filename: str
    file_type: str
    file_size: int
    skills_extracted: list[str]
    experience_years: Optional[float]
    latest_title: Optional[str]
    version_number: int
    created_at: datetime
    ats_score: float = 0.0
    ats_report_id: Optional[str] = None
    missing_keywords: list[str] = []
    formatting_issues: list[str] = []    


class ResumeListItem(BaseModel):
    id: str
    filename: str
    file_type: str
    label: Optional[str]
    version_number: int
    skills_extracted: list[str]
    is_active: bool
    created_at: datetime


class ResumeAnalysisResponse(BaseModel):
    resume_id: str
    analysis: dict
    strengths: list[str]
    weaknesses: list[str]
    improvement_suggestions: list[str]
    target_roles_fit: dict
    overall_score: float


class ResumeOptimizeRequest(BaseModel):
    job_description: Optional[str] = None
    target_role: Optional[str] = None
    repair_focus: Optional[str] = None
    current_issues: list[str] = []


class ResumeOptimizeResponse(BaseModel):
    original_resume_id: str
    new_resume_id: str
    changes_made: list[str]
    improvement_score: float
    optimized_sections: dict
