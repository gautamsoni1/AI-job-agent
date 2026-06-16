"""
Application Agent — Assesses whether a candidate is ready to apply to a
specific job, with success/interview probability and blockers.
GROQ + MISTRAL ONLY.
"""
import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory

logger = structlog.get_logger()


class ApplicationAgent(BaseAgent):
    agent_name = "application_agent"

    async def assess_readiness(self, job: dict, resume_text: str, memory: UserMemory) -> dict:
        """Run a full readiness check before the user submits an application."""
        template = self._load_prompt("application_agent", "readiness_check")
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            job_title=job.get("title", ""),
            job_company=job.get("company", ""),
            job_description=(job.get("description", "") or "")[:3000],
            resume_text=resume_text[:5000],
            latest_ats_score=memory.latest_ats_score,
        )
        system_prompt = (
            "You are a Senior Career Advisor performing a final application readiness check. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.25)
        return self._normalize_readiness(result)

    def _normalize_readiness(self, result: dict) -> dict:
        return {
            "readiness_score": float(result.get("readiness_score", 0) or 0),
            "success_probability": float(result.get("success_probability", 0) or 0),
            "interview_probability": float(result.get("interview_probability", 0) or 0),
            "blockers": result.get("blockers", []) or [],
            "recommended_actions": result.get("recommended_actions", []) or [],
            "apply_now": bool(result.get("apply_now", False)),
            "best_resume_version": result.get("best_resume_version", ""),
            "estimated_response_days": int(result.get("estimated_response_days", 14) or 14),
        }