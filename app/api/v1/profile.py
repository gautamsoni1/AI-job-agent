"""
Profile API Endpoints — Get and Update User Profile
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.repositories.profile_repo import ProfileRepository
from app.schemas.profile import UpdateProfileRequest, ProfileResponse

router = APIRouter()


@router.get("/", response_model=ProfileResponse)
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = ProfileRepository(db)
    profile = await repo.find_by_user(str(current_user["_id"]))
    if not profile:
        # Create empty profile
        now = datetime.now(timezone.utc)
        empty = {
            "user_id": str(current_user["_id"]),
            "headline": None, "summary": None, "linkedin_url": None,
            "github_url": None, "portfolio_url": None, "target_role": None,
            "target_salary_min": None, "target_salary_max": None,
            "work_type": None, "education": [], "experience": [],
            "projects": [], "certifications": [], "languages": [],
            "created_at": now, "updated_at": now,
        }
        pid = await repo.insert(empty)
        empty["_id"] = pid
        profile = empty

    return _to_response(profile)


@router.put("/", response_model=ProfileResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = ProfileRepository(db)
    update_data = body.model_dump(exclude_none=True)

    # Convert nested models to dicts
    for field in ("education", "experience", "projects", "certifications"):
        if field in update_data:
            update_data[field] = [
                item.model_dump() if hasattr(item, "model_dump") else item
                for item in update_data[field]
            ]

    pid = await repo.upsert_for_user(str(current_user["_id"]), update_data)
    profile = await repo.find_by_user(str(current_user["_id"]))
    return _to_response(profile)


def _to_response(p: dict) -> ProfileResponse:
    return ProfileResponse(
        id=str(p.get("_id", "")),
        user_id=p.get("user_id", ""),
        headline=p.get("headline"),
        summary=p.get("summary"),
        linkedin_url=p.get("linkedin_url"),
        github_url=p.get("github_url"),
        portfolio_url=p.get("portfolio_url"),
        target_role=p.get("target_role"),
        target_salary_min=p.get("target_salary_min"),
        target_salary_max=p.get("target_salary_max"),
        work_type=p.get("work_type"),
        education=p.get("education", []),
        experience=p.get("experience", []),
        projects=p.get("projects", []),
        certifications=p.get("certifications", []),
        languages=p.get("languages", []),
        created_at=p.get("created_at", datetime.now(timezone.utc)),
        updated_at=p.get("updated_at", datetime.now(timezone.utc)),
    )