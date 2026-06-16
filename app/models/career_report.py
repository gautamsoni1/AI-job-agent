from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class CareerReportDocument(BaseModel):
    """Stores AI-generated career roadmaps, gap analyses, and weekly goal plans."""
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    user_id: str
    report_type: str  # roadmap | gap_analysis | weekly_goals
    target_role: Optional[str] = None
    content: dict = {}
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True