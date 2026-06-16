"""
AI Timeline API — Chronological log of all AI actions for the user
"""
from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.repositories.timeline_repo import TimelineRepository

router = APIRouter()


@router.get("/")
async def get_timeline(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    event_type: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = TimelineRepository(db)
    skip = (page - 1) * page_size
    user_id = str(current_user["_id"])

    if event_type:
        events = await repo.find_by_event_type(user_id, event_type, limit=page_size)
    else:
        events = await repo.find_by_user(user_id, skip=skip, limit=page_size)

    for e in events:
        e["_id"] = str(e["_id"])

    total = await repo.count({"user_id": user_id})
    return {"success": True, "events": events, "total": total, "page": page, "page_size": page_size}


@router.get("/today")
async def get_today_count(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = TimelineRepository(db)
    count = await repo.count_today(str(current_user["_id"]))
    return {"success": True, "events_today": count}


@router.get("/summary")
async def get_timeline_summary(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    user_id = str(current_user["_id"])
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {"_id": "$event_type", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    cursor = db["ai_timeline"].aggregate(pipeline)
    results = await cursor.to_list(length=50)
    return {"success": True, "summary": {r["_id"]: r["count"] for r in results}}