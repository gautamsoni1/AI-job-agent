from pydantic import BaseModel
from typing import Optional


class PipelineJobItem(BaseModel):
    job_id: str
    title: str
    company: str
    location: Optional[str] = None
    apply_link: Optional[str] = None
    match_score: Optional[float] = None
    relevance_score: Optional[float] = None
    salary_range: Optional[str] = None
    required_skills: list[str] = []
    source: Optional[str] = None
    scout_report: dict = {}
    match_report: dict = {}


class PipelineRunResponse(BaseModel):
    pipeline_id: str
    resume_id: str
    target_role: Optional[str] = None
    initial_ats_score: float
    final_ats_score: float
    ats_iterations: int
    resume_optimized: bool
    optimized_resume_id: Optional[str] = None
    jobs_found: int
    jobs: list[PipelineJobItem]
    before_apply_sheet_url: Optional[str] = None
    message: str


class BulkApplyResponse(BaseModel):
    pipeline_id: str
    total_jobs: int
    applied_count: int
    manual_apply_count: int
    failed_count: int
    after_apply_sheet_url: Optional[str] = None
    results: list[dict]


class SingleApplyResponse(BaseModel):
    pipeline_id: str
    job_id: str
    status: str
    application_id: Optional[str] = None
    message: str