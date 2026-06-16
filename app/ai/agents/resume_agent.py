"""
Resume Agent — Analyzes resumes at a deep level, rewrites bullet points,
finds weaknesses, and generates ATS-optimized versions for different roles.
GROQ + MISTRAL ONLY.
"""
import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory

logger = structlog.get_logger()


class ResumeAgent(BaseAgent):
    agent_name = "resume_agent"

    async def analyze(self, resume_text: str, target_role: str, memory: UserMemory) -> dict:
        """Deep AI analysis of a resume against an (optional) target role."""
        template = self._load_prompt("resume_agent", "analyze")
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            target_role=target_role or "Not specified — use the user's preferred roles from context",
            resume_text=resume_text[:6000],
        )
        system_prompt = (
            "You are a Senior Resume Strategist and Career Coach. "
            "Always respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.3)
        return self._normalize_analysis(result)

    async def rewrite(self, resume_text: str, job_description: str, memory: UserMemory) -> dict:
        """Rewrite resume content to align with a target job description."""
        template = self._load_prompt("resume_agent", "rewrite")
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            resume_text=resume_text[:6000],
            job_description=job_description[:3000],
        )
        system_prompt = (
            "You are a Senior Resume Writer specializing in ATS-optimized, achievement-driven rewrites. "
            "Optimize for strict external resume checkers such as Enhancv, Jobscan, and ResumeWorded. "
            "Never invent experience the candidate doesn't have. Respond with valid JSON only."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.2)
        return self._normalize_rewrite(result)

    async def find_weaknesses(self, resume_text: str, memory: UserMemory) -> dict:
        """Identify weaknesses, buzzwords, and missing sections in a resume."""
        template = self._load_prompt("resume_agent", "weakness_finder")
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            resume_text=resume_text[:6000],
        )
        system_prompt = (
            "You are a brutally honest Senior Technical Recruiter. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.25)
        return self._normalize_weaknesses(result)

    async def generate_versions(self, base_resume_text: str, target_roles: list[str], memory: UserMemory) -> list[dict]:
        """Generate multiple ATS-optimized resume versions, one per target role."""
        versions = []
        for role in target_roles:
            template = self._load_prompt("resume_agent", "rewrite")
            prompt = self._render_prompt(
                template,
                user_memory=memory.to_prompt_context(),
                resume_text=base_resume_text[:6000],
                job_description=f"A {role} role at a competitive technology company. "
                                 f"Optimize this resume specifically for {role} positions.",
            )
            system_prompt = (
                "You are a Senior Resume Writer creating a role-specific resume version. "
                "Respond with valid JSON only."
            )
            result = await self._call_groq_json(system_prompt, prompt, temperature=0.35)
            normalized = self._normalize_rewrite(result)
            normalized["label"] = f"{role} Optimized"
            normalized["target_role"] = role
            versions.append(normalized)
        return versions

    def _normalize_analysis(self, result: dict) -> dict:
        analysis = result.get("analysis", {}) or {}
        return {
            "overall_score": float(result.get("overall_score", 0) or 0),
            "analysis": {
                "structure_score": float(analysis.get("structure_score", 0) or 0),
                "impact_score": float(analysis.get("impact_score", 0) or 0),
                "clarity_score": float(analysis.get("clarity_score", 0) or 0),
                "role_alignment_score": float(analysis.get("role_alignment_score", 0) or 0),
                "summary": analysis.get("summary", ""),
                "ats_blockers": analysis.get("ats_blockers", []) or [],
                "section_diagnostics": analysis.get("section_diagnostics", {}) or {},
                "critical_issues": analysis.get("critical_issues", []) or [],
                "moderate_issues": analysis.get("moderate_issues", []) or [],
                "minor_issues": analysis.get("minor_issues", []) or [],
                "quick_wins": analysis.get("quick_wins", []) or [],
            },
            "strengths": result.get("strengths", []) or [],
            "weaknesses": result.get("weaknesses", []) or [],
            "improvement_suggestions": result.get("improvement_suggestions", []) or [],
            "target_roles_fit": result.get("target_roles_fit", {}) or {},
        }

    def _normalize_rewrite(self, result: dict) -> dict:
        return {
            "full_name": result.get("full_name", ""),
            "contact": result.get("contact", {}) or {},
            "rewritten_summary": result.get("rewritten_summary", ""),
            "rewritten_experience": result.get("rewritten_experience", []) or [],
            "rewritten_skills": result.get("rewritten_skills", []) or [],
            "education": result.get("education", []) or [],
            "projects": result.get("projects", []) or [],
            "changes_made": result.get("changes_made", []) or [],
            "improvement_score": float(result.get("improvement_score", 0) or 0),
            "keywords_added": result.get("keywords_added", []) or [],
            "remaining_risks": result.get("remaining_risks", []) or [],
            "quality_audit": result.get("quality_audit", {}) or {},
        }

    def _normalize_weaknesses(self, result: dict) -> dict:
        return {
            "critical_issues": result.get("critical_issues", []) or [],
            "moderate_issues": result.get("moderate_issues", []) or [],
            "minor_issues": result.get("minor_issues", []) or [],
            "buzzwords_to_remove": result.get("buzzwords_to_remove", []) or [],
            "missing_sections": result.get("missing_sections", []) or [],
            "severity_score": float(result.get("severity_score", 0) or 0),
            "quick_wins": result.get("quick_wins", []) or [],
        }
