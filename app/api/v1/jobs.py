"""
Jobs API Endpoints — Discovery, Listing, Scouting, Matching, Saving
"""
import re
from ast import literal_eval
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError
from app.config import get_settings
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.job import JobDiscoverRequest, JobDescribeRequest, JobResponse, JobListResponse
from app.services.apify_service import ApifyService
from app.services.google_sheets_service import GoogleSheetsService
from app.ai.orchestrator import AIOrchestrator
from app.utils.date_utils import is_recently_posted, parse_flexible_date

router = APIRouter()
settings = get_settings()


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
        body.max_age_days,
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
    background_tasks.add_task(
        _sync_to_sheets, job, result.data.get("overall_match", 0), 0.0,
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
    j["title"] = _display_value(j.get("title"), "Role not provided")
    j["company"] = _display_value(j.get("company"), "Company not provided")
    j["location"] = _display_value(j.get("location"), "Location not provided")
    j["description"] = _plain_text(j.get("description"), "Description not provided")
    j["experience_required"] = _display_value(j.get("experience_required"), "Experience not provided")
    j["salary_range"] = _display_value(j.get("salary_range"), "Salary not provided")
    j["employment_type"] = _display_value(j.get("employment_type"), "Employment type not provided")
    j["work_type"] = _display_value(j.get("work_type"), "Work type not provided")
    j["apply_link"] = _display_value(j.get("apply_link"), "Apply link not provided")
    j["source"] = _display_value(j.get("source"), "Source not provided")
    j["deadline"] = _display_value(j.get("deadline"), "Deadline not provided")
    j["bond"] = _display_value(j.get("bond"), "Bond not provided")
    j["package"] = _display_value(j.get("package"), "Package not provided")
    j["company_logo"] = _display_value(j.get("company_logo"), "Company logo not provided")
    j.setdefault("required_skills", [])
    j["salary_min"] = _display_value(j.get("salary_min"), "Salary min not provided")
    j["salary_max"] = _display_value(j.get("salary_max"), "Salary max not provided")
    j.setdefault("scout_report", {})
    j.setdefault("discovered_at", j.get("created_at") or j.get("fetched_at") or datetime.utcnow())
    j["posted_date"] = _display_value(j.get("posted_date") or j.get("posted_at"), "Posted date not provided")
    for key in ("raw_data", "fetched_at"):
        j.pop(key, None)
    return j


def _display_value(value, fallback: str) -> str:
    if value is None:
        return fallback
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            value = literal_eval(value)
        except (ValueError, SyntaxError):
            pass
    if isinstance(value, str) and not value.strip():
        return fallback
    if isinstance(value, dict):
        for key in ("name", "title", "value", "text"):
            if value.get(key):
                return str(value[key])
        return fallback
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item) or fallback
    return str(value)


def _plain_text(value, fallback: str) -> str:
    text = _display_value(value, fallback)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or fallback


def _parse_job_datetime(value):
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


async def _sync_to_sheets(job: dict, match_score: float = 0.0, ats_score: float = 0.0):
    """Best-effort sync of a job row to Google Sheets. Skips silently if
    GOOGLE_SHEET_ID isn't configured, and never raises — a Sheets outage
    should never break job discovery or matching."""
    if not settings.GOOGLE_SHEET_ID:
        return
    try:
        sheets = GoogleSheetsService()
        duplicate = await sheets.check_duplicate(
            job.get("company") or "Company not provided",
            job.get("title") or "Role not provided",
            job.get("apply_link") or "",
        )
        if duplicate:
            return
        await sheets.sync_job(job, match_score=match_score, ats_score=ats_score)
    except Exception as e:
        import structlog
        structlog.get_logger().warning("sheets_sync_failed", error=str(e))


async def _run_job_discovery(db, user_id: str, keywords: list, locations: list, experience_level: str, max_results: int, max_age_days: int = 30):
    try:
        apify = ApifyService()
        raw_jobs = await apify.fetch_jobs(keywords, locations, experience_level, max_results)
        repo = JobRepository(db)
        orchestrator = AIOrchestrator(db)

        skipped_old = 0
        for raw_job in raw_jobs:
            posted_value = raw_job.get("posted_at") or raw_job.get("posted_date")
            if not is_recently_posted(posted_value, max_age_days=max_age_days):
                skipped_old += 1
                continue

            raw_job["user_id"] = user_id
            raw_job["created_at"] = datetime.now(timezone.utc)
            raw_job["discovered_at"] = raw_job["created_at"]
            raw_job["updated_at"] = datetime.now(timezone.utc)
            raw_job["is_saved"] = False
            raw_job["is_deleted"] = False
            raw_job.setdefault("required_skills", [])
            raw_job.setdefault("salary_min", None)
            raw_job.setdefault("salary_max", None)
            raw_job.setdefault("work_type", "Work type not provided")
            raw_job.setdefault("bond", "Bond not provided")
            raw_job.setdefault("package", "Package not provided")
            raw_job.setdefault("posted_date", parse_flexible_date(posted_value))

            existing = await repo.check_duplicate(user_id, raw_job.get("apply_link", ""))
            if existing:
                continue

            job_ids = await repo.bulk_insert_jobs([raw_job])
            if job_ids:
                job_with_id = dict(raw_job)
                job_with_id["_id"] = job_ids[0]
                relevance_score = 0.0
                try:
                    result = await orchestrator.execute(
                        agent_name="job_scout_agent",
                        task="scout",
                        user_id=user_id,
                        payload={"job": job_with_id},
                    )
                    await repo.update_scout_report(job_ids[0], result.data)
                    relevance_score = result.data.get("relevance_score", 0.0)
                except Exception:
                    pass

                await _sync_to_sheets(job_with_id, match_score=relevance_score, ats_score=0.0)

        await db["ai_timeline"].insert_one({
            "user_id": user_id,
            "event_type": "JOB_DISCOVERED",
            "title": f"Discovered {len(raw_jobs) - skipped_old} jobs",
            "description": f"Keywords: {', '.join(keywords)}",
            "metadata": {
                "count": len(raw_jobs) - skipped_old,
                "skipped_old": skipped_old,
                "keywords": keywords,
                "locations": locations,
            },
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
