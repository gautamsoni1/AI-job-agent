"""
Job Matching Agent — Matches a resume against a specific job description and
produces a multi-dimensional match report with gap analysis.
GROQ + MISTRAL ONLY.
"""
import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory
from app.utils.keyword_extractor import extract_job_keywords, keyword_coverage

logger = structlog.get_logger()

_MATCH_PROMPT = """You are a Senior Technical Recruiter specializing in matching candidates to job descriptions with precision scoring across multiple dimensions.

USER CONTEXT:
{user_memory}

CANDIDATE RESUME:
{resume_text}

JOB DESCRIPTION:
Title: {job_title}
Company: {job_company}
Description: {job_description}
Required Skills: {required_skills}

Think step by step:
1. Compare the candidate's skills against the job's required and nice-to-have skills.
2. Compare the candidate's experience level and years against what the role requires.
3. Assess keyword overlap between the resume and job description.
4. Compare education background against any stated requirements.
5. Identify specific gaps and, for each, suggest how the candidate could close it and how long it might take.
6. Write a clear explanation of the overall match and a recommendation.

Return a JSON object with EXACTLY this structure and nothing else:
{{
  "overall_match": <0-100 float>,
  "skill_match": <0-100 float>,
  "experience_match": <0-100 float>,
  "keyword_match": <0-100 float>,
  "education_match": <0-100 float>,
  "gap_analysis": [
    {{"skill": "<skill>", "importance": "HIGH" | "MEDIUM" | "LOW", "how_to_fill": "<specific action>", "time_estimate": "<time estimate>"}}
  ],
  "match_explanation": "<human-readable summary of the overall match>",
  "recommendation": "<should the candidate apply, and what to do first>"
}}
"""


class JobMatchingAgent(BaseAgent):
    agent_name = "job_matching_agent"

    async def match(self, resume_text: str, job: dict, memory: UserMemory) -> dict:
        """Compute a detailed match report between a resume and a job."""
        prompt = _MATCH_PROMPT.format(
            user_memory=memory.to_prompt_context(),
            resume_text=resume_text[:6000],
            job_title=job.get("title", ""),
            job_company=job.get("company", ""),
            job_description=(job.get("description", "") or "")[:3000],
            required_skills=", ".join(job.get("required_skills", []) or []) or "Not specified",
        )
        system_prompt = (
            "You are a Senior Technical Recruiter performing resume-to-job matching. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.2)
        normalized = self._normalize_match(result)

        if normalized["keyword_match"] == 0:
            job_keywords = extract_job_keywords(job.get("description", ""))
            coverage = keyword_coverage(resume_text, job_keywords)
            if coverage:
                matched = sum(1 for v in coverage.values() if v)
                normalized["keyword_match"] = round((matched / len(coverage)) * 100, 2)

        return normalized

    def _normalize_match(self, result: dict) -> dict:
        return {
            "overall_match": float(result.get("overall_match", 0) or 0),
            "skill_match": float(result.get("skill_match", 0) or 0),
            "experience_match": float(result.get("experience_match", 0) or 0),
            "keyword_match": float(result.get("keyword_match", 0) or 0),
            "education_match": float(result.get("education_match", 0) or 0),
            "gap_analysis": result.get("gap_analysis", []) or [],
            "match_explanation": result.get("match_explanation", ""),
            "recommendation": result.get("recommendation", ""),
        }