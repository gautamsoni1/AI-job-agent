"""
Interview Prep API Endpoints — Question Generation, Answer Evaluation
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.interview import InterviewKitResponse, EvaluateAnswerRequest, AnswerFeedbackResponse, QA
from app.ai.orchestrator import AIOrchestrator

router = APIRouter()


@router.post("/prep/{job_id}", response_model=InterviewKitResponse, status_code=201)
async def generate_interview_prep(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    job_repo = JobRepository(db)
    resume_repo = ResumeRepository(db)

    job = await job_repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", job_id)

    resume = await resume_repo.find_active_by_user(str(current_user["_id"]))
    resume_text = resume.get("raw_text", "") if resume else ""

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="interview_agent",
        task="generate_questions",
        user_id=str(current_user["_id"]),
        payload={"job": job, "resume_text": resume_text},
    )

    data = result.data

    # Store interview kit
    kit_doc = {
        "user_id": str(current_user["_id"]),
        "job_id": job_id,
        "company": job.get("company", ""),
        "role": job.get("title", ""),
        "technical_questions": data.get("technical_questions", []),
        "behavioral_questions": data.get("behavioral_questions", []),
        "company_specific_questions": data.get("company_specific_questions", []),
        "questions_to_ask_interviewer": data.get("questions_to_ask_interviewer", []),
        "preparation_checklist": data.get("preparation_checklist", []),
        "created_at": datetime.now(timezone.utc),
    }
    await db["interview_kits"].insert_one(kit_doc)

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "INTERVIEW_PREP_GENERATED",
        f"Interview prep generated for {job.get('title')} at {job.get('company')}",
        {"job_id": job_id},
    )

    def _to_qa_list(items: list) -> list[QA]:
        return [
            QA(
                question=q.get("question", ""),
                model_answer=q.get("model_answer", ""),
                tips=q.get("tips", []),
                framework=q.get("framework"),
            )
            for q in items
        ]

    return InterviewKitResponse(
        job_id=job_id,
        company=job.get("company", ""),
        role=job.get("title", ""),
        technical_questions=_to_qa_list(data.get("technical_questions", [])),
        behavioral_questions=_to_qa_list(data.get("behavioral_questions", [])),
        company_specific_questions=_to_qa_list(data.get("company_specific_questions", [])),
        questions_to_ask_interviewer=data.get("questions_to_ask_interviewer", []),
        preparation_checklist=data.get("preparation_checklist", []),
        created_at=datetime.now(timezone.utc),
    )


@router.post("/evaluate", response_model=AnswerFeedbackResponse)
async def evaluate_answer(
    body: EvaluateAnswerRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="interview_agent",
        task="evaluate_answer",
        user_id=str(current_user["_id"]),
        payload={
            "question": body.question,
            "answer": body.answer,
            "job_context": body.job_context,
        },
    )

    data = result.data
    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "INTERVIEW_ANSWER_EVALUATED",
        f"Answer evaluated — Score: {data.get('score', 0)}/10",
        {"score": data.get("score", 0)},
    )

    return AnswerFeedbackResponse(
        score=data.get("score", 0.0),
        strengths=data.get("strengths", []),
        improvements=data.get("improvements", []),
        better_answer_example=data.get("better_answer_example", ""),
        framework_used=data.get("framework_used"),
    )


@router.get("/history")
async def get_interview_history(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db["interview_kits"].find(
        {"user_id": str(current_user["_id"])},
        sort=[("created_at", -1)]
    ).limit(20)
    kits = await cursor.to_list(length=20)
    for k in kits:
        k["_id"] = str(k["_id"])
    return {"success": True, "history": kits}


async def _log_timeline(db, user_id: str, event_type: str, title: str, metadata: dict):
    from datetime import datetime
    await db["ai_timeline"].insert_one({
        "user_id": user_id, "event_type": event_type,
        "title": title, "description": title,
        "metadata": metadata, "created_at": datetime.utcnow(),
    })