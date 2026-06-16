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
    location: str
    description: str
    required_skills: list[str]
    experience_required: str
    salary_min: str
    salary_max: str
    salary_range: str
    employment_type: str
    work_type: str
    apply_link: str
    source: str
    posted_date: str
    deadline: str
    bond: str
    package: str
    company_logo: str
    scout_report: dict
    discovered_at: datetime


class JobListResponse(BaseModel):
    jobs: list[JobResponse]
    total: int
    page: int
    page_size: int
