"""
Pipeline API — single entry point: upload resume → analyze → ATS score/auto-
improve → job discovery/scouting/matching → sheets → apply-all / apply-one.

RATE LIMIT: Each verified user gets 1 free pipeline run per 24 hours.
After 24 hours the limit resets and they can run again.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.progress import progress_manager

from app.core.dependencies import get_db, get_verified_user
from app.core.exceptions import NotFoundError, ValidationError
from app.services.pipeline_service import PipelineService
from app.schemas.pipeline import PipelineRunResponse, BulkApplyResponse, SingleApplyResponse

router = APIRouter()

# ---------------------------------------------------------------------------
# RATE LIMIT HELPER
# ---------------------------------------------------------------------------

async def _check_pipeline_rate_limit(user_id: str, db: AsyncIOMotorDatabase) -> None:
    """
    Enforce the 1-run-per-24-hours limit.

    Looks at pipeline_runs collection for any document belonging to this
    user that was created within the last 24 hours. If found, raises a
    ValidationError (HTTP 422) with a clear message telling the user
    exactly when their limit resets.

    The index `pipeline_user_created` (added in database.py) makes this
    query a fast indexed scan even with millions of pipeline_runs rows.
    """
    window_start = datetime.now(timezone.utc) - timedelta(hours=24)

    # Convert to naive UTC for comparison (MongoDB stores naive datetimes
    # via datetime.utcnow() calls throughout the codebase).
    window_start_naive = window_start.replace(tzinfo=None)

    recent_run = await db["pipeline_runs"].find_one(
        {
            "user_id": user_id,
            "created_at": {"$gte": window_start_naive},
        },
        # Only fetch the timestamp field we need — no full document load
        {"created_at": 1},
    )

    if recent_run:
        run_time: datetime = recent_run["created_at"]
        # Ensure naive for arithmetic
        if run_time.tzinfo is not None:
            run_time = run_time.replace(tzinfo=None)
        reset_at = run_time + timedelta(hours=24)
        now_naive = datetime.utcnow()
        time_left = reset_at - now_naive
        hours_left = int(time_left.total_seconds() // 3600)
        minutes_left = int((time_left.total_seconds() % 3600) // 60)

        raise ValidationError(
            f"Free plan allows 1 pipeline run per 24 hours. "
            f"Your limit resets in {hours_left}h {minutes_left}m. "
            f"Next run available at {reset_at.strftime('%Y-%m-%d %H:%M UTC')}."
        )


# ---------------------------------------------------------------------------
# ENDPOINTS
# ---------------------------------------------------------------------------

@router.post("/run", response_model=PipelineRunResponse, status_code=201)
async def run_pipeline(
    file: UploadFile = File(..., description="Resume file — PDF or DOCX"),
    target_role: Optional[str] = Form(None),
    job_description: Optional[str] = Form(None),
    locations: Optional[str] = Form(None, description="Comma-separated, e.g. 'Bangalore,Remote'"),
    max_jobs: int = Form(15),
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    # ── Rate limit check ────────────────────────────────────────────────
    await _check_pipeline_rate_limit(str(current_user["_id"]), db)
    # ────────────────────────────────────────────────────────────────────

    if file.content_type not in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        raise ValidationError("Only PDF and DOCX files are allowed.")

    file_bytes = await file.read()
    location_list = [loc.strip() for loc in locations.split(",") if loc.strip()] if locations else None

    service = PipelineService(db)
    result = await service.run_pipeline(
        user=current_user,
        file_bytes=file_bytes,
        filename=file.filename or "resume",
        target_role=target_role,
        job_description=job_description,
        locations=location_list,
        max_jobs=max(1, min(max_jobs, 40)),
    )
    return result


@router.post("/run/start")
async def start_pipeline(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Resume file — PDF or DOCX"),
    target_role: Optional[str] = Form(None),
    job_description: Optional[str] = Form(None),
    locations: Optional[str] = Form(None),
    max_jobs: int = Form(15),
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Pipeline ko background mein start karta hai aur turant run_id +
    websocket_url return kar deta hai. Live progress ke liye us URL par
    connect karo; final result DONE event ke 'data' field mein aayega."""

    # ── Rate limit check (same guard for async start path) ──────────────
    await _check_pipeline_rate_limit(str(current_user["_id"]), db)
    # ────────────────────────────────────────────────────────────────────

    if file.content_type not in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        raise ValidationError("Only PDF and DOCX files are allowed.")

    file_bytes = await file.read()
    location_list = [loc.strip() for loc in locations.split(",") if loc.strip()] if locations else None
    run_id = str(uuid.uuid4())

    service = PipelineService(db)
    background_tasks.add_task(
        service.run_pipeline_tracked,
        run_id,
        current_user,
        file_bytes,
        file.filename or "resume",
        target_role,
        job_description,
        location_list,
        max(1, min(max_jobs, 40)),
    )
    return {
        "success": True,
        "run_id": run_id,
        "websocket_url": f"/api/v1/pipeline/ws/{run_id}",
    }


@router.websocket("/ws/{run_id}")
async def pipeline_progress_ws(websocket: WebSocket, run_id: str):
    await websocket.accept()
    queue = await progress_manager.subscribe(run_id)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event)
            if event["stage"] in ("DONE", "ERROR"):
                break
    except WebSocketDisconnect:
        pass
    finally:
        await progress_manager.unsubscribe(run_id, queue)


@router.get("/history")
async def pipeline_history(
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    service = PipelineService(db)
    runs = await service.list_runs(str(current_user["_id"]))
    return {"success": True, "runs": runs}


@router.get("/rate-limit-status")
async def rate_limit_status(
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Frontend can call this to show the user their current rate limit state
    without attempting a run. Returns can_run, next_run_at, hours_remaining.
    """
    window_start = datetime.now(timezone.utc) - timedelta(hours=24)
    window_start_naive = window_start.replace(tzinfo=None)

    recent_run = await db["pipeline_runs"].find_one(
        {
            "user_id": str(current_user["_id"]),
            "created_at": {"$gte": window_start_naive},
        },
        {"created_at": 1},
    )

    if not recent_run:
        return {
            "success": True,
            "can_run": True,
            "next_run_at": None,
            "hours_remaining": 0,
            "message": "You can run the pipeline now.",
        }

    run_time: datetime = recent_run["created_at"]
    if run_time.tzinfo is not None:
        run_time = run_time.replace(tzinfo=None)
    reset_at = run_time + timedelta(hours=24)
    time_left = reset_at - datetime.utcnow()
    hours_left = max(0, int(time_left.total_seconds() // 3600))
    minutes_left = max(0, int((time_left.total_seconds() % 3600) // 60))

    return {
        "success": True,
        "can_run": False,
        "next_run_at": reset_at.strftime("%Y-%m-%d %H:%M UTC"),
        "hours_remaining": hours_left,
        "minutes_remaining": minutes_left,
        "message": (
            f"Free plan: 1 pipeline run per 24 hours. "
            f"Next run available in {hours_left}h {minutes_left}m."
        ),
    }


@router.get("/{pipeline_id}")
async def get_pipeline(
    pipeline_id: str,
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    service = PipelineService(db)
    data = await service.get_pipeline_detail(str(current_user["_id"]), pipeline_id)
    return {"success": True, "data": data}


@router.post("/{pipeline_id}/apply-all", response_model=BulkApplyResponse)
async def apply_all(pipeline_id: str, current_user: dict = Depends(get_verified_user), db: AsyncIOMotorDatabase = Depends(get_db)):
    service = PipelineService(db)
    result = await service.apply_to_all_jobs(str(current_user["_id"]), pipeline_id)
    return BulkApplyResponse(
        pipeline_id=pipeline_id,
        total_jobs=result["total"],
        applied_count=result["applied_count"],
        manual_apply_count=result["manual_count"],
        failed_count=result["failed_count"],
        after_apply_sheet_url=f"/api/v1/pipeline/{pipeline_id}/download/after-apply",
        results=result["results"],
    )


@router.post("/{pipeline_id}/apply/{job_id}", response_model=SingleApplyResponse)
async def apply_one(
    pipeline_id: str,
    job_id: str,
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    service = PipelineService(db)
    result = await service.apply_to_job(str(current_user["_id"]), pipeline_id, job_id)
    status = result["status"]
    if result["already_applied"]:
        message = f"Already on record — status: {status}."
    elif status == "APPLIED":
        message = "Resume + cover letter emailed directly to the recruiter."
    elif status == "MANUAL_APPLY_REQUIRED":
        message = "No recruiter email found on this posting — finish applying via the portal link."
    else:
        message = "Could not complete the application automatically — please apply manually."
    return SingleApplyResponse(
        pipeline_id=pipeline_id,
        job_id=job_id,
        status=status,
        message=message,
    )


@router.get("/{pipeline_id}/download/before-apply")
async def download_before_apply_sheet(
    pipeline_id: str,
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    service = PipelineService(db)
    path = await service.get_sheet_path(str(current_user["_id"]), pipeline_id, "before")
    if not path or not os.path.exists(path):
        raise NotFoundError("Jobs sheet", pipeline_id)
    return FileResponse(
        path=path, filename=f"jobs_found_{pipeline_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/{pipeline_id}/download/after-apply")
async def download_after_apply_sheet(
    pipeline_id: str,
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    service = PipelineService(db)
    path = await service.get_sheet_path(str(current_user["_id"]), pipeline_id, "after")
    if not path or not os.path.exists(path):
        raise NotFoundError("Application results sheet", pipeline_id)
    return FileResponse(
        path=path, filename=f"application_results_{pipeline_id}.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )