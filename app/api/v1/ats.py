"""
ATS API Endpoints — Score, History, Trend, Improvement Plan
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.resume_repo import ResumeRepository
from app.repositories.ats_repo import ATSRepository
from app.repositories.job_repo import JobRepository
from app.schemas.ats import ATSScoreRequest, ATSScoreResponse, ATSTrendResponse, ATSTrendItem
from app.ai.orchestrator import AIOrchestrator

router = APIRouter()


@router.post("/score", response_model=ATSScoreResponse, status_code=201)
async def score_resume(
    body: ATSScoreRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    resume_repo = ResumeRepository(db)
    resume = await resume_repo.get_by_id(body.resume_id)
    if not resume or resume.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Resume", body.resume_id)

    job_description = body.job_description or ""
    if not job_description.strip():
        job_repo = JobRepository(db)
        jobs = await job_repo.find_by_user(str(current_user["_id"]), limit=1)
        if jobs:
            job = jobs[0]
            job_description = _job_to_description(job)
    if not job_description.strip():
        raise ValidationError("No job found for this user. Add a job first or provide job_description.")

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="ats_agent",
        task="score",
        user_id=str(current_user["_id"]),
        payload={
            "resume_text": resume.get("raw_text", ""),
            "job_description": job_description,
        },
    )
    if not result.success:
        raise ValidationError(f"ATS scoring failed: {result.error or 'AI service error'}")

    data = result.data
    report_doc = {
        "user_id": str(current_user["_id"]),
        "resume_id": body.resume_id,
        "job_description_snippet": job_description[:200],
        "ats_score": data.get("ats_score", 0.0),
        "keyword_coverage": data.get("keyword_coverage", {}),
        "missing_keywords": data.get("missing_keywords", []),
        "section_analysis": data.get("section_analysis", {}),
        "formatting_issues": data.get("formatting_issues", []),
        "skill_relevance": data.get("skill_relevance", 0.0),
        "industry_alignment": data.get("industry_alignment", 0.0),
        "improvement_plan": data.get("improvement_plan", []),
        "predicted_pass_rate": data.get("predicted_pass_rate", 0.0),
        "full_report": data,
        "created_at": datetime.now(timezone.utc),
    }

    ats_repo = ATSRepository(db)
    report_id = await ats_repo.insert(report_doc)

    # Update user's latest ATS score
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"latest_ats_score": data.get("ats_score", 0.0)}}
    )

    background_tasks.add_task(
        _log_timeline,
        db,
        str(current_user["_id"]),
        "ATS_SCORED",
        f"ATS Score: {data.get('ats_score', 0):.0f}/100",
        {"report_id": report_id, "score": data.get("ats_score", 0)},
    )

    return ATSScoreResponse(
        report_id=report_id,
        ats_score=data.get("ats_score", 0.0),
        keyword_coverage=data.get("keyword_coverage", {}),
        missing_keywords=data.get("missing_keywords", []),
        section_analysis=data.get("section_analysis", {}),
        formatting_issues=data.get("formatting_issues", []),
        predicted_pass_rate=data.get("predicted_pass_rate", 0.0),
        improvement_plan=data.get("improvement_plan", []),
        skill_relevance=data.get("skill_relevance"),
        industry_alignment=data.get("industry_alignment"),
    )


@router.get("/history")
async def get_ats_history(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    ats_repo = ATSRepository(db)
    reports = await ats_repo.find_by_user(str(current_user["_id"]))
    return {"success": True, "reports": [_serialize_report(r) for r in reports]}


@router.get("/trend", response_model=ATSTrendResponse)
async def get_ats_trend(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    ats_repo = ATSRepository(db)
    trend_docs = await ats_repo.get_trend(str(current_user["_id"]))
    items = [
        ATSTrendItem(
            report_id=str(d.get("_id", "")),
            ats_score=d.get("ats_score", 0.0),
            job_description_snippet=d.get("job_description_snippet"),
            created_at=d.get("created_at", datetime.now(timezone.utc)),
        )
        for d in trend_docs
    ]
    first_score = items[0].ats_score if items else None
    latest_score = items[-1].ats_score if items else None
    improvement = round(latest_score - first_score, 2) if (first_score and latest_score) else None
    return ATSTrendResponse(trend=items, first_score=first_score, latest_score=latest_score, improvement=improvement)


@router.get("/{report_id}")
async def get_ats_report(
    report_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    ats_repo = ATSRepository(db)
    report = await ats_repo.get_by_id(report_id)
    if not report or report.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("ATS Report", report_id)
    return {"success": True, "data": _serialize_report(report)}


@router.post("/{report_id}/improvement-plan")
async def get_improvement_plan(
    report_id: str,
    job_description: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    ats_repo = ATSRepository(db)
    report = await ats_repo.get_by_id(report_id)
    if not report or report.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("ATS Report", report_id)

    resume_repo = ResumeRepository(db)
    resume = await resume_repo.find_active_by_user(str(current_user["_id"]))
    if not resume:
        raise NotFoundError("Active Resume", "none")

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="ats_agent",
        task="improvement_plan",
        user_id=str(current_user["_id"]),
        payload={
            "resume_text": resume.get("raw_text", ""),
            "job_description": job_description,
            "latest_report": report,
        },
    )
    return {"success": True, "data": result.data}


def _serialize_report(r: dict) -> dict:
    r = dict(r)
    if "_id" in r:
        r["_id"] = str(r["_id"])
    r.pop("full_report", None)
    return r


async def _log_timeline(db, user_id: str, event_type: str, title: str, metadata: dict):
    from datetime import datetime
    await db["ai_timeline"].insert_one({
        "user_id": user_id,
        "event_type": event_type,
        "title": title,
        "description": title,
        "metadata": metadata,
        "created_at": datetime.utcnow(),
    })


def _job_to_description(job: dict) -> str:
    parts = [
        f"Title: {job.get('title', '')}",
        f"Company: {job.get('company', '')}",
        f"Location: {job.get('location', '')}",
        job.get("description", ""),
    ]
    if job.get("requirements"):
        parts.append("Requirements: " + ", ".join(str(item) for item in job["requirements"]))
    if job.get("required_skills"):
        parts.append("Required skills: " + ", ".join(str(item) for item in job["required_skills"]))
    if job.get("nice_to_have_skills"):
        parts.append("Nice to have: " + ", ".join(str(item) for item in job["nice_to_have_skills"]))
    return "\n".join(part for part in parts if part)
