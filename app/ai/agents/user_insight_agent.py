"""
User Insight Agent — Analyzes a user's job search behavior (jobs viewed vs
applied, ATS trend, response rates, skill-gap patterns) and produces
actionable insights.
GROQ + MISTRAL ONLY.
"""
import json

import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory

logger = structlog.get_logger()


class UserInsightAgent(BaseAgent):
    agent_name = "user_insight_agent"

    async def generate_insights(self, memory: UserMemory, recent_jobs: list[dict] = None) -> dict:
        """Generate behavioral insights for the user based on their memory and activity."""
        template = self._load_prompt("career_agent", "user_insights")
        activity_data = self._summarize_activity(memory, recent_jobs or [])
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            activity_data=activity_data,
        )
        system_prompt = (
            "You are a Senior Behavioral Data Analyst specializing in job-search behavior. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.3)
        return self._normalize_insights(result)

    def _summarize_activity(self, memory: UserMemory, recent_jobs: list[dict]) -> str:
        ats_scores = [s.score for s in memory.ats_trend]
        data = {
            "jobs_viewed_count": memory.jobs_viewed_count,
            "jobs_saved_count": memory.jobs_saved_count,
            "jobs_applied_count": memory.jobs_applied_count,
            "application_success_rate": memory.application_success_rate,
            "interview_rate": memory.interview_rate,
            "ats_score_history": ats_scores,
            "skills": memory.skills[:30],
            "preferred_roles": memory.preferred_roles,
            "preferred_locations": memory.preferred_locations,
            "recent_jobs_sample": [
                {
                    "title": j.get("title", ""),
                    "company": j.get("company", ""),
                    "required_skills": j.get("required_skills", [])[:8],
                    "is_saved": j.get("is_saved", False),
                }
                for j in recent_jobs[:20]
            ],
        }
        return json.dumps(data, default=str)

    def _normalize_insights(self, result: dict) -> dict:
        return {
            "behavior_summary": result.get("behavior_summary", ""),
            "engagement_ratio_analysis": result.get("engagement_ratio_analysis", ""),
            "ats_progress_analysis": result.get("ats_progress_analysis", ""),
            "response_rate_analysis": result.get("response_rate_analysis", ""),
            "preferred_company_patterns": result.get("preferred_company_patterns", []) or [],
            "recurring_skill_gaps": result.get("recurring_skill_gaps", []) or [],
            "inferred_salary_expectation": result.get("inferred_salary_expectation", ""),
            "recommendations": result.get("recommendations", []) or [],
        }