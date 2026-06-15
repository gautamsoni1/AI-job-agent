"""
Career Coach Agent — Generates career roadmaps, gap analyses, and weekly
action plans. All outputs are specific, actionable, and timeline-bound.
GROQ + MISTRAL ONLY.
"""
import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory

logger = structlog.get_logger()


class CareerCoachAgent(BaseAgent):
    agent_name = "career_coach_agent"

    async def generate_roadmap(self, memory: UserMemory) -> dict:
        """Generate a short/mid/long-term career roadmap."""
        template = self._load_prompt("career_agent", "roadmap")
        prompt = self._render_prompt(template, user_memory=memory.to_prompt_context())
        system_prompt = (
            "You are a Senior Career Coach who builds detailed, timeline-bound career roadmaps. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.35)
        return self._normalize_roadmap(result)

    async def analyze_gap(self, target_role: str, memory: UserMemory) -> dict:
        """Analyze the gap between the user's current profile and a target role."""
        template = self._load_prompt("career_agent", "gap_analysis")
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            target_role=target_role,
        )
        system_prompt = (
            "You are a Senior Career Strategist specializing in role-transition gap analysis. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.3)
        return self._normalize_gap_analysis(result)

    async def weekly_goals(self, memory: UserMemory) -> dict:
        """Generate a weekly action plan for the user's job search."""
        template = self._load_prompt("career_agent", "weekly_goals")
        prompt = self._render_prompt(template, user_memory=memory.to_prompt_context())
        system_prompt = (
            "You are a Senior Career Coach who creates focused weekly action plans for job seekers. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.35)
        return self._normalize_weekly_goals(result)

    def _normalize_roadmap(self, result: dict) -> dict:
        return {
            "short_term_goals": result.get("short_term_goals", []) or [],
            "mid_term_goals": result.get("mid_term_goals", []) or [],
            "long_term_goals": result.get("long_term_goals", []) or [],
            "recommended_skills": result.get("recommended_skills", []) or [],
            "recommended_certifications": result.get("recommended_certifications", []) or [],
            "recommended_projects": result.get("recommended_projects", []) or [],
            "summary": result.get("summary", ""),
        }

    def _normalize_gap_analysis(self, result: dict) -> dict:
        return {
            "target_role": result.get("target_role", ""),
            "current_level": result.get("current_level", ""),
            "target_level": result.get("target_level", ""),
            "skill_gaps": result.get("skill_gaps", []) or [],
            "experience_gaps": result.get("experience_gaps", []) or [],
            "education_gaps": result.get("education_gaps", []) or [],
            "time_to_ready": result.get("time_to_ready", ""),
            "action_plan": result.get("action_plan", []) or [],
        }

    def _normalize_weekly_goals(self, result: dict) -> dict:
        return {
            "week_focus": result.get("week_focus", ""),
            "goals": result.get("goals", []) or [],
            "daily_tasks": result.get("daily_tasks", []) or [],
            "skill_to_practice": result.get("skill_to_practice", ""),
            "job_to_apply_count": int(result.get("job_to_apply_count", 5) or 5),
            "networking_goal": result.get("networking_goal", ""),
        }