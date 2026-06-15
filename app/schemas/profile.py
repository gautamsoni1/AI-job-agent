from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class EducationEntryRequest(BaseModel):
    institution: str
    degree: str
    field: str
    start_year: int
    end_year: Optional[int] = None
    gpa: Optional[float] = None


class ExperienceEntryRequest(BaseModel):
    company: str
    title: str
    location: Optional[str] = None
    start_date: str
    end_date: Optional[str] = None
    current: bool = False
    description: list[str] = []
    technologies: list[str] = []


class ProjectEntryRequest(BaseModel):
    name: str
    description: str
    technologies: list[str] = []
    url: Optional[str] = None


class CertificationEntryRequest(BaseModel):
    name: str
    issuer: str
    year: int
    url: Optional[str] = None


class UpdateProfileRequest(BaseModel):
    headline: Optional[str] = None
    summary: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    target_role: Optional[str] = None
    target_salary_min: Optional[int] = None
    target_salary_max: Optional[int] = None
    work_type: Optional[str] = None
    education: Optional[list[EducationEntryRequest]] = None
    experience: Optional[list[ExperienceEntryRequest]] = None
    projects: Optional[list[ProjectEntryRequest]] = None
    certifications: Optional[list[CertificationEntryRequest]] = None
    languages: Optional[list[str]] = None


class ProfileResponse(BaseModel):
    id: str
    user_id: str
    headline: Optional[str]
    summary: Optional[str]
    linkedin_url: Optional[str]
    github_url: Optional[str]
    portfolio_url: Optional[str]
    target_role: Optional[str]
    target_salary_min: Optional[int]
    target_salary_max: Optional[int]
    work_type: Optional[str]
    education: list[dict]
    experience: list[dict]
    projects: list[dict]
    certifications: list[dict]
    languages: list[str]
    created_at: datetime
    updated_at: datetime