from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class ResumeDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str
    filename: str
    file_path: str
    file_type: str  # pdf | docx
    file_size: int
    raw_text: str
    parsed_sections: dict = {}
    skills_extracted: list[str] = []
    experience_years: Optional[float] = None
    latest_title: Optional[str] = None
    is_active: bool = True
    version_number: int = 1
    parent_resume_id: Optional[str] = None
    label: Optional[str] = None  # "ATS Optimized", "Data Science v2", etc.
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True