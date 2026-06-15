"""
Cover Letter Agent — Generates personalized cover letters referencing
specific company details, role requirements, and the candidate's real achievements.
GROQ + MISTRAL ONLY.
"""
import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory

logger = structlog.get_logger()


class CoverLetterAgent(BaseAgent):
    agent_name = "cover_letter_agent"

    async def generate(
        self,
        resume_text: str,
        job: dict,
        company_name: str,
        memory: UserMemory,
        tone: str = "professional",
    ) -> dict:
        """Generate a personalized cover letter for the given job and resume."""
        tone = tone if tone in ("professional", "friendly", "formal") else "professional"
        template = self._load_prompt("cover_letter_agent", "generate")
        prompt = self._render_prompt(
            template,
            tone=tone,
            user_memory=memory.to_prompt_context(),
            resume_text=resume_text[:5000],
            job_title=job.get("title", ""),
            company_name=company_name or job.get("company", ""),
            job_description=(job.get("description", "") or "")[:3000],
        )
        system_prompt = (
            f"You are a Senior Career Writer who writes personalized, {tone} cover letters. "
            "Respond with valid JSON only, matching the requested schema exactly. "
            "Never use generic placeholder phrases like '[Company Name]' — always use the real company name provided."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.4)
        normalized = self._normalize_letter(result, tone)
        normalized["full_text"] = self._assemble_full_text(normalized, company_name or job.get("company", ""), job.get("title", ""))
        return normalized

    def _normalize_letter(self, result: dict, tone: str) -> dict:
        return {
            "subject_line": result.get("subject_line", ""),
            "greeting": result.get("greeting", "Dear Hiring Manager,"),
            "body": result.get("body", ""),
            "closing": result.get("closing", "Sincerely,"),
            "key_points_referenced": result.get("key_points_referenced", []) or [],
            "achievements_highlighted": result.get("achievements_highlighted", []) or [],
            "tone": tone,
        }

    def _assemble_full_text(self, letter: dict, company_name: str, role_title: str) -> str:
        parts = []
        if letter.get("subject_line"):
            parts.append(f"Subject: {letter['subject_line']}")
            parts.append("")
        parts.append(letter.get("greeting", "Dear Hiring Manager,"))
        parts.append("")
        parts.append(letter.get("body", ""))
        parts.append("")
        parts.append(letter.get("closing", "Sincerely,"))
        return "\n".join(parts).strip()