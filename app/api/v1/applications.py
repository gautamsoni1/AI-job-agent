"""
Applications API Endpoints — Create, Track, Status, Stats, Readiness
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.application import (
    CreateApplicationRequest, UpdateStatusRequest,
    ApplicationResponse, ApplicationStatsResponse, BulkApplicationRequest
)
from app.ai.orchestrator import AIOrchestrator

router = APIRouter()


@router.post("/", response_model=ApplicationResponse, status_code=201)
async def create_application(
    body: CreateApplicationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    app_repo = ApplicationRepository(db)
    job_repo = JobRepository(db)

    job = await job_repo.get_by_id(body.job_id)
    if not job:
        raise NotFoundError("Job", body.job_id)

    existing = await app_repo.find_by_user_and_job(str(current_user["_id"]), body.job_id)
    if existing:
        return _to_app_response(existing)

    now = datetime.now(timezone.utc)
    app_doc = {
        "user_id": str(current_user["_id"]),
        "job_id": body.job_id,
        "resume_id": body.resume_id,
        "cover_letter_id": body.cover_letter_id,
        "status": "APPLIED",
        "applied_at": now,
        "notes": body.notes,
        "status_history": [{"status": "APPLIED", "changed_at": now}],
        "created_at": now,
        "updated_at": now,
    }
    app_id = await app_repo.insert(app_doc)
    app_doc["_id"] = app_id

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "APPLICATION_SUBMITTED",
        f"Applied to {job.get('title')} at {job.get('company')}",
        {"app_id": app_id, "job_id": body.job_id},
    )

    return _to_app_response(app_doc)


@router.post("/bulk")
async def bulk_apply(
    body: BulkApplicationRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    app_repo = ApplicationRepository(db)
    created_ids = []
    now = datetime.now(timezone.utc)

    for job_id in body.job_ids:
        existing = await app_repo.find_by_user_and_job(str(current_user["_id"]), job_id)
        if existing:
            continue
        app_doc = {
            "user_id": str(current_user["_id"]),
            "job_id": job_id,
            "resume_id": body.resume_id,
            "status": "APPLIED",
            "applied_at": now,
            "status_history": [{"status": "APPLIED", "changed_at": now}],
            "created_at": now,
            "updated_at": now,
        }
        app_id = await app_repo.insert(app_doc)
        created_ids.append(app_id)

    return {"success": True, "created_count": len(created_ids), "application_ids": created_ids}


@router.get("/", response_model=list[ApplicationResponse])
async def list_applications(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    app_repo = ApplicationRepository(db)
    skip = (page - 1) * page_size
    apps = await app_repo.find_by_user(str(current_user["_id"]), skip=skip, limit=page_size)
    return [_to_app_response(a) for a in apps]


@router.get("/stats", response_model=ApplicationStatsResponse)
async def get_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    app_repo = ApplicationRepository(db)
    stats = await app_repo.get_stats(str(current_user["_id"]))
    response_rate = await app_repo.get_response_rate(str(current_user["_id"]))
    interview_rate = await app_repo.get_interview_rate(str(current_user["_id"]))
    total = stats.get("total", 0)
    offers = stats.get("by_status", {}).get("OFFER", 0)
    offer_rate = round((offers / total * 100), 2) if total > 0 else 0.0

    return ApplicationStatsResponse(
        total=total,
        by_status=stats.get("by_status", {}),
        application_rate=round(total / 30, 2),
        interview_rate=interview_rate,
        offer_rate=offer_rate,
        average_readiness_score=None,
    )


@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(
    app_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    app_repo = ApplicationRepository(db)
    app = await app_repo.get_by_id(app_id)
    if not app or app.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Application", app_id)
    return _to_app_response(app)


@router.put("/{app_id}/status")
async def update_application_status(
    app_id: str,
    body: UpdateStatusRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    app_repo = ApplicationRepository(db)
    ok = await app_repo.update_status(app_id, str(current_user["_id"]), body.status.value, body.notes or "")
    if not ok:
        raise NotFoundError("Application", app_id)

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "APPLICATION_STATUS_CHANGED",
        f"Application status changed to {body.status.value}",
        {"app_id": app_id, "new_status": body.status.value},
    )
    return {"success": True, "message": f"Status updated to {body.status.value}"}


@router.delete("/{app_id}")
async def delete_application(
    app_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    app_repo = ApplicationRepository(db)
    ok = await app_repo.delete(app_id)
    if not ok:
        raise NotFoundError("Application", app_id)
    return {"success": True, "message": "Application deleted."}


@router.post("/{app_id}/assess")
async def assess_readiness(
    app_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    app_repo = ApplicationRepository(db)
    app = await app_repo.get_by_id(app_id)
    if not app or app.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Application", app_id)

    job_repo = JobRepository(db)
    job = await job_repo.get_by_id(app.get("job_id", ""))
    if not job:
        raise NotFoundError("Job", app.get("job_id", ""))

    resume_repo = ResumeRepository(db)
    resume = await resume_repo.find_active_by_user(str(current_user["_id"]))
    if not resume:
        raise NotFoundError("Active resume", "none")

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="application_agent",
        task="assess_readiness",
        user_id=str(current_user["_id"]),
        payload={"job": job, "resume_text": resume.get("raw_text", "")},
    )

    # Update readiness score on application
    await app_repo.update(app_id, {
        "readiness_score": result.data.get("readiness_score", 0),
        "success_probability": result.data.get("success_probability", 0),
        "interview_probability": result.data.get("interview_probability", 0),
    })

    return {"success": True, "assessment": result.data}


def _to_app_response(a: dict) -> ApplicationResponse:
    return ApplicationResponse(
        id=str(a.get("_id", "")),
        job_id=a.get("job_id", ""),
        resume_id=a.get("resume_id"),
        cover_letter_id=a.get("cover_letter_id"),
        status=a.get("status", "APPLIED"),
        readiness_score=a.get("readiness_score"),
        success_probability=a.get("success_probability"),
        interview_probability=a.get("interview_probability"),
        applied_at=a.get("applied_at"),
        notes=a.get("notes"),
        interview_date=a.get("interview_date"),
        created_at=a.get("created_at", datetime.now(timezone.utc)),
    )


async def _log_timeline(db, user_id: str, event_type: str, title: str, metadata: dict):
    from datetime import datetime
    await db["ai_timeline"].insert_one({
        "user_id": user_id, "event_type": event_type,
        "title": title, "description": title,
        "metadata": metadata, "created_at": datetime.utcnow(),
    })