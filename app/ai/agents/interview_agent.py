"""
Interview Preparation Agent — Generates a full interview kit (technical,
behavioral, company-specific questions) and evaluates practice answers.
GROQ + MISTRAL ONLY.
"""
import structlog

from app.ai.agents.base_agent import BaseAgent
from app.ai.memory import UserMemory

logger = structlog.get_logger()


class InterviewAgent(BaseAgent):
    agent_name = "interview_agent"

    async def generate_questions(self, job: dict, resume_text: str, memory: UserMemory) -> dict:
        """Generate a full interview preparation kit for a job."""
        template = self._load_prompt("interview_agent", "question_generator")
        prompt = self._render_prompt(
            template,
            user_memory=memory.to_prompt_context(),
            job_title=job.get("title", ""),
            job_company=job.get("company", ""),
            job_description=(job.get("description", "") or "")[:3000],
            resume_text=resume_text[:5000],
        )
        system_prompt = (
            "You are a Senior Hiring Manager and Interview Coach building a realistic interview prep kit. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.4, max_tokens=6000)
        return self._normalize_kit(result)

    async def evaluate_answer(self, question: str, answer: str, job_context: str) -> dict:
        """Evaluate a candidate's practice answer to an interview question."""
        template = self._load_prompt("interview_agent", "answer_evaluator")
        prompt = self._render_prompt(
            template,
            question=question,
            answer=answer,
            job_context=job_context[:1500],
        )
        system_prompt = (
            "You are a Senior Interview Coach giving candid, constructive feedback. "
            "Respond with valid JSON only, matching the requested schema exactly."
        )
        result = await self._call_groq_json(system_prompt, prompt, temperature=0.3)
        return self._normalize_feedback(result)

    def _normalize_qa_list(self, items: list) -> list[dict]:
        normalized = []
        for item in items or []:
            if not isinstance(item, dict):
                continue
            normalized.append({
                "question": item.get("question", ""),
                "model_answer": item.get("model_answer", ""),
                "tips": item.get("tips", []) or [],
                "framework": item.get("framework"),
            })
        return normalized

    def _normalize_kit(self, result: dict) -> dict:
        return {
            "technical_questions": self._normalize_qa_list(result.get("technical_questions", [])),
            "behavioral_questions": self._normalize_qa_list(result.get("behavioral_questions", [])),
            "company_specific_questions": self._normalize_qa_list(result.get("company_specific_questions", [])),
            "questions_to_ask_interviewer": result.get("questions_to_ask_interviewer", []) or [],
            "preparation_checklist": result.get("preparation_checklist", []) or [],
        }

    def _normalize_feedback(self, result: dict) -> dict:
        score = result.get("score", 0) or 0
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = 0.0
        return {
            "score": round(min(max(score, 0.0), 10.0), 2),
            "strengths": result.get("strengths", []) or [],
            "improvements": result.get("improvements", []) or [],
            "better_answer_example": result.get("better_answer_example", ""),
            "framework_used": result.get("framework_used"),
        }