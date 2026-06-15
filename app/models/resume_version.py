from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class ResumeVersionDocument(BaseModel):
    """Snapshot of a resume at a point in time — created on upload, rewrite, or optimization."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    resume_id: str
    user_id: str
    version_number: int
    label: Optional[str] = None  # "ATS Optimized", "Data Science v2", etc.
    raw_text: str
    parsed_sections: dict = {}
    skills_extracted: list[str] = []
    source: str = "upload"  # upload | ai_rewrite | ai_generated_version
    changes_made: list[str] = []
    target_role: Optional[str] = None
    job_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True