from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field
from app.models.user import PyObjectId


class JobDocument(BaseModel):
    id: Optional[PyObjectId] = Field(default=None, alias="_id")
    title: str
    company: str
    location: Optional[str] = None
    description: str
    requirements: list[str] = []
    required_skills: list[str] = []
    nice_to_have_skills: list[str] = []
    experience_required: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: str = "USD"
    employment_type: Optional[str] = None  # full-time | part-time | contract
    work_type: Optional[str] = None  # remote | hybrid | onsite
    apply_link: Optional[str] = None
    source: Optional[str] = None  # linkedin | indeed | naukri
    posted_date: Optional[datetime] = None
    deadline: Optional[datetime] = None
    is_active: bool = True
    scout_report: Optional[dict] = None
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True