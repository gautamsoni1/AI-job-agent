from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class QA(BaseModel):
    question: str
    model_answer: str
    tips: list[str] = []
    framework: Optional[str] = None  # STAR, etc.


class InterviewKitResponse(BaseModel):
    job_id: str
    company: str
    role: str
    technical_questions: list[QA]
    behavioral_questions: list[QA]
    company_specific_questions: list[QA]
    questions_to_ask_interviewer: list[str]
    preparation_checklist: list[str]
    created_at: datetime


class EvaluateAnswerRequest(BaseModel):
    question: str
    answer: str
    job_context: str


class AnswerFeedbackResponse(BaseModel):
    score: float  # 0-10
    strengths: list[str]
    improvements: list[str]
    better_answer_example: str
    framework_used: Optional[str]