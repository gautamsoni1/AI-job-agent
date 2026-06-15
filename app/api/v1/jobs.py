"""
Jobs API Endpoints — Discovery, Listing, Scouting, Matching, Saving
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.job import JobDiscoverRequest, JobDescribeRequest, JobResponse, JobListResponse
from app.services.apify_service import ApifyService
from app.ai.orchestrator import AIOrchestrator

router = APIRouter()


@router.post("/discover")
async def discover_jobs(
    body: JobDiscoverRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    background_tasks.add_task(
        _run_job_discovery,
        db,
        str(current_user["_id"]),
        body.keywords,
        body.locations,
        body.experience_level,
        body.max_results,
    )
    return {"success": True, "message": f"Job discovery started. Searching for {', '.join(body.keywords)} in {', '.join(body.locations)}."}


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    skip = (page - 1) * page_size
    jobs = await repo.find_by_user(str(current_user["_id"]), skip=skip, limit=page_size)
    total = await repo.count_by_user(str(current_user["_id"]))
    return JobListResponse(
        jobs=[_to_job_response(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/saved")
async def get_saved_jobs(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    jobs = await repo.find_saved_by_user(str(current_user["_id"]))
    return {"success": True, "jobs": [_to_job_response(j) for j in jobs]}


@router.get("/matches")
async def get_top_matches(
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    jobs = await repo.find_top_matches(str(current_user["_id"]), limit=limit)
    return {"success": True, "jobs": [_to_job_response(j) for j in jobs]}


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", job_id)
    # Track view
    await db["jobs"].update_one({"_id": __import__("bson").ObjectId(job_id)}, {"$set": {"last_viewed_at": datetime.utcnow()}})
    return {"success": True, "data": _to_job_response(job)}


@router.post("/{job_id}/scout")
async def scout_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", job_id)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="job_scout_agent",
        task="scout",
        user_id=str(current_user["_id"]),
        payload={"job": job},
    )

    await repo.update_scout_report(job_id, result.data)

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "JOB_SCOUTED", f"Scouted: {job.get('title')} at {job.get('company')}",
        {"job_id": job_id, "relevance_score": result.data.get("relevance_score", 0)},
    )
    return {"success": True, "scout_report": result.data}


@router.post("/{job_id}/match")
async def match_job(
    job_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    job = await repo.get_by_id(job_id)
    if not job:
        raise NotFoundError("Job", job_id)

    resume_repo = ResumeRepository(db)
    resume = await resume_repo.find_active_by_user(str(current_user["_id"]))
    if not resume:
        raise NotFoundError("Active resume", "none")

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="job_matching_agent",
        task="match",
        user_id=str(current_user["_id"]),
        payload={"resume_text": resume.get("raw_text", ""), "job": job},
    )

    await repo.update_match_score(job_id, result.data.get("overall_match", 0), result.data)

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "JOB_MATCHED", f"Matched: {job.get('title')} at {job.get('company')} — {result.data.get('overall_match', 0):.0f}%",
        {"job_id": job_id, "overall_match": result.data.get("overall_match", 0)},
    )
    return {"success": True, "match_report": result.data}


@router.post("/{job_id}/save")
async def save_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    ok = await repo.save_job(job_id, str(current_user["_id"]))
    if not ok:
        raise NotFoundError("Job", job_id)
    return {"success": True, "message": "Job saved."}


@router.delete("/{job_id}/save")
async def unsave_job(
    job_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = JobRepository(db)
    await repo.unsave_job(job_id, str(current_user["_id"]))
    return {"success": True, "message": "Job unsaved."}


@router.post("/describe")
async def describe_job(
    body: JobDescribeRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="job_scout_agent",
        task="scout",
        user_id=str(current_user["_id"]),
        payload={"job": {
            "title": body.title,
            "company": body.company,
            "description": body.description,
            "location": body.location or "",
        }},
    )
    return {"success": True, "analysis": result.data}


def _to_job_response(j: dict) -> dict:
    j = dict(j)
    if "_id" in j:
        j["id"] = str(j.pop("_id"))
    for key in ("raw_data", "fetched_at"):
        j.pop(key, None)
    return j


async def _run_job_discovery(db, user_id: str, keywords: list, locations: list, experience_level: str, max_results: int):
    try:
        apify = ApifyService()
        raw_jobs = await apify.fetch_jobs(keywords, locations, experience_level, max_results)
        repo = JobRepository(db)
        orchestrator = AIOrchestrator(db)

        for raw_job in raw_jobs:
            raw_job["user_id"] = user_id
            raw_job["created_at"] = datetime.now(timezone.utc)
            raw_job["updated_at"] = datetime.now(timezone.utc)
            raw_job["is_saved"] = False
            raw_job["is_deleted"] = False

            existing = await repo.check_duplicate(user_id, raw_job.get("apply_link", ""))
            if existing:
                continue

            job_ids = await repo.bulk_insert_jobs([raw_job])
            if job_ids:
                job_with_id = dict(raw_job)
                job_with_id["_id"] = job_ids[0]
                # Scout in background
                try:
                    result = await orchestrator.execute(
                        agent_name="job_scout_agent",
                        task="scout",
                        user_id=user_id,
                        payload={"job": job_with_id},
                    )
                    await repo.update_scout_report(job_ids[0], result.data)
                except Exception:
                    pass

        await db["ai_timeline"].insert_one({
            "user_id": user_id,
            "event_type": "JOB_DISCOVERED",
            "title": f"Discovered {len(raw_jobs)} jobs",
            "description": f"Keywords: {', '.join(keywords)}",
            "metadata": {"count": len(raw_jobs), "keywords": keywords, "locations": locations},
            "created_at": datetime.utcnow(),
        })
    except Exception as e:
        import structlog
        structlog.get_logger().error("job_discovery_failed", error=str(e))


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