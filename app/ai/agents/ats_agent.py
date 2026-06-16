"""
ATS Agent — Deep ATS analysis. Not just a score, but a full diagnostic report
with section-level analysis, keyword coverage, and a prioritized improvement plan.
GROQ + MISTRAL ONLY.
"""
import structlog
import re

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
        job_keywords = extract_job_keywords(job_description)
        deterministic_coverage = fallback_coverage(resume_text, job_keywords)
        normalized["keyword_coverage"] = {
            **{
                key: bool(value)
                for key, value in normalized["keyword_coverage"].items()
                if isinstance(value, bool)
            },
            **deterministic_coverage,
        }
        missing = list(normalized["missing_keywords"])
        missing.extend([kw for kw, present in deterministic_coverage.items() if not present])
        normalized["missing_keywords"] = list(dict.fromkeys(missing))[:25]
        normalized = self._apply_external_checker_penalties(normalized, resume_text, job_keywords)

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
            "ats_score": self._clamp_score(result.get("ats_score", 0)),
            "keyword_coverage": result.get("keyword_coverage", {}) or {},
            "missing_keywords": result.get("missing_keywords", []) or [],
            "section_analysis": normalized_sections,
            "formatting_issues": result.get("formatting_issues", []) or [],
            "skill_relevance": self._clamp_score(result.get("skill_relevance", 0)),
            "industry_alignment": self._clamp_score(result.get("industry_alignment", 0)),
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

    def _clamp_score(self, value) -> float:
        try:
            score = float(value or 0)
        except (TypeError, ValueError):
            score = 0.0
        return max(0.0, min(100.0, score))

    def _apply_external_checker_penalties(self, data: dict, resume_text: str, job_keywords: list[str]) -> dict:
        text = resume_text or ""
        lower = text.lower()
        issues = list(data.get("formatting_issues", []))
        penalty = 0.0

        contact_ok = bool(re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)) and bool(
            re.search(r"\+?\d[\d().\-\s]{7,}\d", text)
        )
        if not contact_ok:
            penalty += 8
            issues.append("Contact section is incomplete; include email and phone.")

        required_sections = ("professional summary", "skills", "work experience", "education")
        missing_sections = [section for section in required_sections if section not in lower]
        if missing_sections:
            penalty += 6 * len(missing_sections)
            issues.append("Missing standard sections: " + ", ".join(missing_sections))

        bullets = [line.strip(" -•\t") for line in text.splitlines() if line.strip().startswith(("-", "•"))]
        if bullets:
            impact_pattern = (
                r"(\d+%?|\$[\d,.]+|\b\d+\+?\b|x\b|times|users|clients|hours|days|weeks|"
                r"revenue|cost|accuracy|latency|performance|saved|reduced|increased|improved|"
                r"automated|streamlined|accelerated|production|stakeholder|cross-functional|"
                r"client-facing|maintainability|reliability|scalability|reporting|workflow|"
                r"manual work|user experience|quality|throughput|efficiency)"
            )
            metric_count = sum(bool(re.search(impact_pattern, b, re.I)) for b in bullets)
            metric_ratio = metric_count / len(bullets)
            if metric_ratio < 0.55:
                penalty += 12
                issues.append("Too few bullets quantify impact; add measurable outcomes where truthful.")
            starts = [b.split()[0].lower().strip(",.;:") for b in bullets if b.split()]
            repeated_starts = {s for s in starts if starts.count(s) > 1}
            if repeated_starts:
                penalty += min(10, 3 * len(repeated_starts))
                issues.append("Repeated bullet starts detected: " + ", ".join(sorted(repeated_starts)[:5]))
            inconsistent = sum(1 for b in bullets if b and b[-1] not in ".!?")
            if inconsistent:
                penalty += min(6, inconsistent * 1.5)
                issues.append("Bullet punctuation is inconsistent.")
        else:
            penalty += 10
            issues.append("No bullet points detected in work history.")

        grammar_patterns = [
            r"\b(i|im|ive|dont|doesnt|cant|wont)\b",
            r"\s{2,}",
            r"\b(responsible for|worked on|helped with|various things)\b",
            r"\b([A-Za-z]+)\s+\1\b",
        ]
        grammar_hits = sum(len(re.findall(pattern, text, re.I)) for pattern in grammar_patterns)
        if grammar_hits:
            penalty += min(10, grammar_hits * 2)
            issues.append("Grammar, spelling, or weak phrasing issues detected.")

        if job_keywords:
            covered = sum(1 for kw in job_keywords if re.search(r"(?<![a-zA-Z0-9])" + re.escape(kw.lower()) + r"(?![a-zA-Z0-9])", lower))
            coverage_ratio = covered / len(job_keywords)
            if coverage_ratio < 0.65:
                penalty += 14
                issues.append("Tailoring is weak; too many important job keywords are missing.")

        data["ats_score"] = min(95.0, self._clamp_score(data.get("ats_score", 0) - penalty))
        data["formatting_issues"] = list(dict.fromkeys(issues))
        data["predicted_pass_rate"] = round(min(data.get("predicted_pass_rate", 0), data["ats_score"] / 100), 4)
        return data
