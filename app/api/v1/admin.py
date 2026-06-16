"""
Admin API Endpoints — Platform-wide statistics
"""
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_admin

router = APIRouter()


@router.get("/stats")
async def get_platform_stats(
    current_admin: dict = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    total_users = await db["users"].count_documents({})
    active_users = await db["users"].count_documents({"is_active": True})
    total_resumes = await db["resumes"].count_documents({"is_deleted": {"$ne": True}})
    total_jobs = await db["jobs"].count_documents({"is_deleted": {"$ne": True}})
    total_applications = await db["applications"].count_documents({})
    total_cover_letters = await db["cover_letters"].count_documents({})
    total_ats_reports = await db["ats_reports"].count_documents({})

    return {
        "success": True,
        "stats": {
            "total_users": total_users,
            "active_users": active_users,
            "total_resumes": total_resumes,
            "total_jobs": total_jobs,
            "total_applications": total_applications,
            "total_cover_letters": total_cover_letters,
            "total_ats_reports": total_ats_reports,
        },
    }


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_admin: dict = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    skip = (page - 1) * page_size
    cursor = db["users"].find(
        {},
        {"hashed_password": 0, "refresh_tokens": 0, "verification_token": 0},
        sort=[("created_at", -1)],
    ).skip(skip).limit(page_size)
    users = await cursor.to_list(length=page_size)
    for u in users:
        u["_id"] = str(u["_id"])
    total = await db["users"].count_documents({})
    return {"success": True, "users": users, "total": total, "page": page}


@router.get("/jobs")
async def list_all_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_admin: dict = Depends(get_current_admin),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from app.repositories.job_repo import JobRepository
    repo = JobRepository(db)
    skip = (page - 1) * page_size
    jobs = await repo.get_all_for_admin(skip=skip, limit=page_size)
    for j in jobs:
        j["_id"] = str(j["_id"])
    total = await db["jobs"].count_documents({})
    return {"success": True, "jobs": jobs, "total": total, "page": page}