from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class PipelineRunDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str
    resume_id: str
    final_resume_id: Optional[str] = None
    target_role: Optional[str] = None
    target_roles: list[str] = []
    job_description_used: Optional[str] = None
    initial_ats_score: float = 0.0
    final_ats_score: float = 0.0
    ats_iterations: int = 0
    job_ids: list[str] = []
    status: str = "JOBS_READY"  # JOBS_READY | APPLIED
    before_apply_sheet_path: Optional[str] = None
    after_apply_sheet_path: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True