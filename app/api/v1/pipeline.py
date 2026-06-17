"""
Pipeline API — single entry point: upload resume → analyze → ATS score/auto-
improve → job discovery/scouting/matching → sheets → apply-all / apply-one.
"""
import os
from typing import Optional
from chromadb import db
from fastapi import APIRouter, Depends, UploadFile, File, Form
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_verified_user
from app.core.exceptions import NotFoundError, ValidationError
from app.services.pipeline_service import PipelineService
from app.schemas.pipeline import PipelineRunResponse, BulkApplyResponse, SingleApplyResponse

router = APIRouter()


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
    if file.content_type not in (
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ):
        raise ValidationError("Only PDF and DOCX files are allowed.")

    file_bytes = await file.read()
    location_list = [loc.strip() for loc in locations.split(",") if loc.strip()] if locations else None

    service = PipelineService(db)
    return await service.run_pipeline(
        user=current_user,
        file_bytes=file_bytes,
        filename=file.filename or "resume",
        target_role=target_role,
        job_description=job_description,
        locations=location_list,
        max_jobs=max(1, min(max_jobs, 40)),
    )


@router.get("/history")
async def pipeline_history(
    current_user: dict = Depends(get_verified_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    service = PipelineService(db)
    runs = await service.list_runs(str(current_user["_id"]))
    return {"success": True, "runs": runs}


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
        manual_apply_count=result["manual_count"],   # ← yeh line missing thi
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