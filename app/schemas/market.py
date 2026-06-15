from pydantic import BaseModel
from typing import Optional


class SkillTrend(BaseModel):
    skill: str
    demand_score: float
    growth_rate: float
    avg_salary: Optional[int]
    top_companies: list[str]


class TechTrend(BaseModel):
    technology: str
    adoption_rate: float
    job_count: int
    growth_trend: str  # rising | stable | declining


class IndustryTrend(BaseModel):
    industry: str
    hiring_momentum: float
    avg_salary: Optional[int]
    top_roles: list[str]


class SalaryRange(BaseModel):
    role: str
    min_salary: int
    max_salary: int
    median_salary: int
    currency: str = "USD"


class CompanyHiring(BaseModel):
    company: str
    open_positions: int
    top_roles: list[str]
    culture_rating: Optional[float]


class MarketReportResponse(BaseModel):
    top_demanded_skills: list[SkillTrend]
    trending_technologies: list[TechTrend]
    growing_industries: list[IndustryTrend]
    salary_ranges: list[SalaryRange]
    top_hiring_companies: list[CompanyHiring]
    market_summary: str
    user_market_fit_score: Optional[float]