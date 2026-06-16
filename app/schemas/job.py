from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class JobDiscoverRequest(BaseModel):
    keywords: list[str]
    locations: list[str]
    experience_level: str = "mid"
    max_results: int = 50


class JobDescribeRequest(BaseModel):
    title: str
    company: str
    description: str
    location: Optional[str] = None
    apply_link: Optional[str] = None


class JobResponse(BaseModel):
    id: str
    title: str
    company: str
    location: Optional[str]
    description: str
    required_skills: list[str]
    experience_required: Optional[str]
    salary_min: Optional[int]
    salary_max: Optional[int]
    employment_type: Optional[str]
    work_type: Optional[str]
    apply_link: Optional[str]
    source: Optional[str]
    posted_date: Optional[datetime]
    scout_report: Optional[dict]
    discovered_at: datetime


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int