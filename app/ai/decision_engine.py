from dataclasses import dataclass
from typing import Literal

import structlog

from app.ai.groq_client import GroqClient
from app.ai.memory import AIMemoryManager, UserMemory

logger = structlog.get_logger()


@dataclass
class JobEvaluation:
    overall_score: float
    ats_probability: float
    response_probability: float
    career_growth_score: float
    opportunity_score: float
    risk_score: float
    salary_potential_score: float
    should_apply: bool
    apply_priority: Literal["HIGH", "MEDIUM", "LOW", "SKIP"]
    reasoning: str
    action_items: list[str]
    confidence: float


class AIDecisionEngine:
    """
    Multi-dimensional job evaluation engine.
    Every score comes with an explanation — never just a number.
    """

    def __init__(self, groq_client: GroqClient, memory_manager: AIMemoryManager):
        self.groq = groq_client
        self.memory = memory_manager

    async def evaluate_job(self, user_id: str, job: dict) -> JobEvaluation:
        """Evaluate a job opportunity against user profile and return full scoring."""
        user_memory = await self.memory.load_user_memory(user_id)
        return await self._run_evaluation(job, user_memory)

    async def _run_evaluation(self, job: dict, memory: UserMemory) -> JobEvaluation:
        system_prompt = """You are a Senior Career Strategist with 15 years of experience in talent acquisition 
and career coaching. You evaluate job opportunities with surgical precision, weighing multiple 
dimensions to give candidates an honest assessment of whether to apply."""

        user_prompt = f"""
{memory.to_prompt_context()}

JOB TO EVALUATE:
Title: {job.get('title', '')}
Company: {job.get('company', '')}
Location: {job.get('location', '')}
Experience Required: {job.get('experience_required', '')}
Salary: {job.get('salary_range', '')}
Description: {job.get('description', '')[:2000]}

Evaluate this job opportunity across all dimensions. Be honest — if it's a poor fit, say so.

Return a JSON object with EXACTLY this structure:
{{
  "overall_score": <0-100 float>,
  "ats_probability": <0-100 float>,
  "response_probability": <0-100 float>,
  "career_growth_score": <0-100 float>,
  "opportunity_score": <0-100 float>,
  "risk_score": <0-100 float>,
  "salary_potential_score": <0-100 float>,
  "should_apply": <true/false>,
  "apply_priority": <"HIGH" | "MEDIUM" | "LOW" | "SKIP">,
  "reasoning": "<3-5 sentence honest assessment of why this job is/isn't a good fit>",
  "action_items": ["<specific action to take before applying>", ...],
  "confidence": <0.0-1.0 float>
}}
"""

        result = await self.groq.complete_json(system_prompt, user_prompt, temperature=0.2)

        return JobEvaluation(
            overall_score=float(result.get("overall_score", 0)),
            ats_probability=float(result.get("ats_probability", 0)),
            response_probability=float(result.get("response_probability", 0)),
            career_growth_score=float(result.get("career_growth_score", 0)),
            opportunity_score=float(result.get("opportunity_score", 0)),
            risk_score=float(result.get("risk_score", 0)),
            salary_potential_score=float(result.get("salary_potential_score", 0)),
            should_apply=bool(result.get("should_apply", False)),
            apply_priority=result.get("apply_priority", "LOW"),
            reasoning=result.get("reasoning", ""),
            action_items=result.get("action_items", []),
            confidence=float(result.get("confidence", 0.5)),
        )

    async def prioritize_job_list(self, user_id: str, jobs: list[dict]) -> list[dict]:
        """Rank a list of jobs by overall fit. Returns jobs with evaluation attached."""
        memory = await self.memory.load_user_memory(user_id)
        evaluated = []
        for job in jobs:
            try:
                evaluation = await self._run_evaluation(job, memory)
                evaluated.append({**job, "evaluation": evaluation.__dict__})
            except Exception as e:
                logger.error("job_evaluation_failed", job_id=job.get("_id"), error=str(e))
                evaluated.append(job)

        evaluated.sort(key=lambda x: x.get("evaluation", {}).get("overall_score", 0), reverse=True)
        return evaluated

    async def compute_career_health(self, user_id: str) -> dict:
        """Generate a composite career health score from all user signals."""
        memory = await self.memory.load_user_memory(user_id)

        ats_score_normalized = min(memory.latest_ats_score, 100)
        resume_strength = ats_score_normalized * 0.3
        activity_score = min(memory.jobs_applied_count * 5, 100) * 0.2
        success_score = memory.application_success_rate * 0.25
        interview_score = memory.interview_rate * 0.25

        career_health = round(resume_strength + activity_score + success_score + interview_score, 2)

        return {
            "career_health_score": career_health,
            "resume_strength_score": ats_score_normalized,
            "application_success_rate": memory.application_success_rate,
            "interview_conversion_rate": memory.interview_rate,
            "ats_improvement_trend": memory.ats_trend[-1].score - memory.ats_trend[0].score
            if len(memory.ats_trend) >= 2 else 0.0,
            "market_readiness_score": min(len(memory.skills) * 3, 100),
            "job_search_progress_score": min(
                (memory.jobs_viewed_count * 0.5 + memory.jobs_applied_count * 5), 100
            ),
        }