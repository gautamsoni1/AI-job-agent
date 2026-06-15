"""
Market Intelligence Agent — Analyzes job posting data to identify market
trends, in-demand skills, salary ranges, and hiring momentum.
GROQ + MISTRAL ONLY.
"""
import json

import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory

logger = structlog.get_logger()


class MarketIntelAgent(BaseAgent):
    agent_name = "market_intel_agent"

    async def analyze_market(self, jobs: list[dict], memory: UserMemory) -> dict:
        """Analyze a set of job postings and produce a market intelligence report."""
        template = self._load_prompt("market_agent", "trend_analysis")
        jobs_summary = self._summarize_jobs(jobs)
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            jobs_data=jobs_summary,
        )
        system_prompt = (
            "You are a Senior Labor Market Analyst studying job posting data. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.3, max_tokens=6000)
        return self._normalize_report(result)

    def _summarize_jobs(self, jobs: list[dict], limit: int = 40) -> str:
        if not jobs:
            return "No job postings available for analysis."

        summarized = []
        for job in jobs[:limit]:
            summarized.append({
                "title": job.get("title", ""),
                "company": job.get("company", ""),
                "location": job.get("location", ""),
                "required_skills": job.get("required_skills", [])[:10],
                "experience_required": job.get("experience_required", ""),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "employment_type": job.get("employment_type", ""),
                "work_type": job.get("work_type", ""),
            })
        return json.dumps(summarized, default=str)

    def _normalize_report(self, result: dict) -> dict:
        return {
            "top_demanded_skills": result.get("top_demanded_skills", []) or [],
            "trending_technologies": result.get("trending_technologies", []) or [],
            "growing_industries": result.get("growing_industries", []) or [],
            "salary_ranges": result.get("salary_ranges", []) or [],
            "top_hiring_companies": result.get("top_hiring_companies", []) or [],
            "market_summary": result.get("market_summary", ""),
            "user_market_fit_score": float(result.get("user_market_fit_score", 0) or 0),
        }