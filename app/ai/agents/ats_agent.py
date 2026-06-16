"""
ATS Agent — Deep ATS analysis. Not just a score, but a full diagnostic report
with section-level analysis, keyword coverage, and a prioritized improvement plan.
GROQ + MISTRAL ONLY.
"""
import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory
from app.utils.keyword_extractor import extract_job_keywords, keyword_coverage as fallback_coverage

logger = structlog.get_logger()


class ATSAgent(BaseAgent):
    agent_name = "ats_agent"

    async def score(self, resume_text: str, job_description: str, memory: UserMemory) -> dict:
        """Run a full ATS diagnostic of resume vs job description."""
        template = self._load_prompt("ats_agent", "score")
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            resume_text=resume_text[:6000],
            job_description=job_description[:3000],
        )
        system_prompt = (
            "You are a Senior ATS Engineer who evaluates resumes with the precision of an "
            "enterprise ATS system (Workday, Greenhouse, Lever, iCIMS). "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.2)
        normalized = self._normalize_score(result)

        # Cross-check keyword coverage with a deterministic fallback in case
        # the model under-reported missing keywords.
        if not normalized["missing_keywords"]:
            job_keywords = extract_job_keywords(job_description)
            normalized["missing_keywords"] = [
                kw for kw, present in fallback_coverage(resume_text, job_keywords).items() if not present
            ][:15]

        return normalized

    async def improvement_plan(
        self,
        resume_text: str,
        job_description: str,
        latest_report: dict,
        memory: UserMemory,
    ) -> dict:
        """Generate a sequenced ATS improvement plan based on the latest report."""
        template = self._load_prompt("ats_agent", "improvement_plan")
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            latest_report=self._summarize_report(latest_report),
            resume_text=resume_text[:6000],
            job_description=job_description[:3000],
        )
        system_prompt = (
            "You are a Senior ATS Optimization Consultant. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.25)
        return self._normalize_improvement_plan(result)

    def _summarize_report(self, report: dict) -> str:
        if not report:
            return "No previous ATS report available."
        return (
            f"ATS Score: {report.get('ats_score', 0)}\n"
            f"Missing Keywords: {', '.join(report.get('missing_keywords', [])[:15])}\n"
            f"Formatting Issues: {', '.join(report.get('formatting_issues', [])[:10])}\n"
            f"Predicted Pass Rate: {report.get('predicted_pass_rate', 0)}"
        )

    def _normalize_score(self, result: dict) -> dict:
        section_analysis = result.get("section_analysis", {}) or {}
        normalized_sections = {}
        for section, data in section_analysis.items():
            if isinstance(data, dict):
                normalized_sections[section] = {
                    "score": float(data.get("score", 0) or 0),
                    "issues": data.get("issues", []) or [],
                }

        predicted_pass_rate = result.get("predicted_pass_rate", 0) or 0
        try:
            predicted_pass_rate = float(predicted_pass_rate)
        except (TypeError, ValueError):
            predicted_pass_rate = 0.0
        # Normalize to 0-1 range if the model returned a 0-100 value
        if predicted_pass_rate > 1.0:
            predicted_pass_rate = predicted_pass_rate / 100.0

        return {
            "ats_score": float(result.get("ats_score", 0) or 0),
            "keyword_coverage": result.get("keyword_coverage", {}) or {},
            "missing_keywords": result.get("missing_keywords", []) or [],
            "section_analysis": normalized_sections,
            "formatting_issues": result.get("formatting_issues", []) or [],
            "skill_relevance": float(result.get("skill_relevance", 0) or 0),
            "industry_alignment": float(result.get("industry_alignment", 0) or 0),
            "predicted_pass_rate": round(predicted_pass_rate, 4),
            "improvement_plan": result.get("improvement_plan", []) or [],
        }

    def _normalize_improvement_plan(self, result: dict) -> dict:
        return {
            "current_score": float(result.get("current_score", 0) or 0),
            "projected_score_after_fixes": float(result.get("projected_score_after_fixes", 0) or 0),
            "improvement_plan": result.get("improvement_plan", []) or [],
            "keyword_gaps_to_close": result.get("keyword_gaps_to_close", []) or [],
            "formatting_fixes": result.get("formatting_fixes", []) or [],
            "summary": result.get("summary", ""),
        }