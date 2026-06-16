"""
Job Scout Agent — Analyzes raw job postings and generates intelligence reports.
Every job gets a full scout report before showing to the user.
GROQ + MISTRAL ONLY.
"""
import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory

logger = structlog.get_logger()


class JobScoutAgent(BaseAgent):
    agent_name = "job_scout_agent"

    async def scout(self, job: dict, memory: UserMemory) -> dict:
        """Generate a full scout report for a single job posting."""
        template = self._load_prompt("job_agent", "relevance_score")
        salary = job.get("salary_range") or self._format_salary(job)
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            job_title=job.get("title", ""),
            job_company=job.get("company", ""),
            job_location=job.get("location", "") or "Not specified",
            job_experience=job.get("experience_required", "") or "Not specified",
            job_salary=salary or "Not specified",
            job_description=(job.get("description", "") or "")[:3000],
        )
        system_prompt = (
            "You are a Senior Talent Intelligence Analyst scouting job postings on behalf of a candidate. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.25)
        return self._normalize_scout(result)

    def _format_salary(self, job: dict) -> str:
        salary_min = job.get("salary_min")
        salary_max = job.get("salary_max")
        currency = job.get("salary_currency", "USD")
        if salary_min and salary_max:
            return f"{currency} {salary_min:,} - {salary_max:,}"
        if salary_min:
            return f"{currency} {salary_min:,}+"
        return ""

    def _normalize_scout(self, result: dict) -> dict:
        skills_gap = result.get("required_vs_user_skills", {}) or {}
        return {
            "relevance_score": float(result.get("relevance_score", 0) or 0),
            "opportunity_score": float(result.get("opportunity_score", 0) or 0),
            "risk_score": float(result.get("risk_score", 0) or 0),
            "career_growth_score": float(result.get("career_growth_score", 0) or 0),
            "salary_potential_score": float(result.get("salary_potential_score", 0) or 0),
            "why_apply": result.get("why_apply", []) or [],
            "why_avoid": result.get("why_avoid", []) or [],
            "required_vs_user_skills": {
                "matching_skills": skills_gap.get("matching_skills", []) or [],
                "missing_skills": skills_gap.get("missing_skills", []) or [],
            },
            "time_to_apply_readiness": result.get("time_to_apply_readiness", "Not Ready"),
            "recommended_resume_version": result.get("recommended_resume_version", ""),
        }