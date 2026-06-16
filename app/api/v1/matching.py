"""
Matching API Endpoints — Resume to Job Matching
"""
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.matching import MatchRequest, MatchResponse, GapItem
from app.ai.orchestrator import AIOrchestrator

router = APIRouter()


@router.post("/", response_model=MatchResponse)
async def match_resume_to_job(
    body: MatchRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    resume_repo = ResumeRepository(db)
    job_repo = JobRepository(db)

    resume = await resume_repo.get_by_id(body.resume_id)
    if not resume or resume.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Resume", body.resume_id)

    job = await job_repo.get_by_id(body.job_id)
    if not job:
        raise NotFoundError("Job", body.job_id)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="job_matching_agent",
        task="match",
        user_id=str(current_user["_id"]),
        payload={"resume_text": resume.get("raw_text", ""), "job": job},
    )

    data = result.data

    # Store match in DB
    match_doc = {
        "user_id": str(current_user["_id"]),
        "job_id": body.job_id,
        "resume_id": body.resume_id,
        "overall_match": data.get("overall_match", 0.0),
        "skill_match": data.get("skill_match", 0.0),
        "experience_match": data.get("experience_match", 0.0),
        "keyword_match": data.get("keyword_match", 0.0),
        "education_match": data.get("education_match", 0.0),
        "gap_analysis": data.get("gap_analysis", []),
        "match_explanation": data.get("match_explanation", ""),
        "full_report": data,
    }
    from datetime import datetime
    match_doc["created_at"] = datetime.utcnow()
    match_id = await db["job_matches"].insert_one(match_doc)

    gap_items = [
        GapItem(
            skill=g.get("skill", ""),
            importance=g.get("importance", "MEDIUM"),
            how_to_fill=g.get("how_to_fill", ""),
            time_estimate=g.get("time_estimate", ""),
        )
        for g in data.get("gap_analysis", [])
    ]

    return MatchResponse(
        match_id=str(match_id.inserted_id),
        overall_match=data.get("overall_match", 0.0),
        skill_match=data.get("skill_match", 0.0),
        experience_match=data.get("experience_match", 0.0),
        keyword_match=data.get("keyword_match", 0.0),
        education_match=data.get("education_match", 0.0),
        gap_analysis=gap_items,
        match_explanation=data.get("match_explanation", ""),
        recommendation=data.get("recommendation", ""),
    )


@router.get("/history")
async def get_match_history(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cursor = db["job_matches"].find(
        {"user_id": str(current_user["_id"])},
        sort=[("created_at", -1)]
    ).limit(50)
    matches = await cursor.to_list(length=50)
    for m in matches:
        m["_id"] = str(m["_id"])
        m.pop("full_report", None)
    return {"success": True, "matches": matches}