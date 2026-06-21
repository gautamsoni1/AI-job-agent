from datetime import datetime, timedelta
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class ApplicationRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "applications")

    async def find_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
        cursor = self.collection.find(
            {"user_id": user_id},
            sort=[("applied_at", -1)]
        ).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_by_user_and_job(self, user_id: str, job_id: str) -> Optional[dict]:
        return await self.collection.find_one({"user_id": user_id, "job_id": job_id})

    async def update_status(self, app_id: str, user_id: str, status: str, notes: str = "") -> bool:
        log_entry = {
            "status": status,
            "changed_at": datetime.utcnow(),
            "notes": notes
        }
        result = await self.collection.update_one(
            {"_id": ObjectId(app_id), "user_id": user_id},
            {
                "$set": {"status": status, "updated_at": datetime.utcnow()},
                "$push": {"status_history": log_entry}
            }
        )
        return result.modified_count > 0

    async def get_stats(self, user_id: str) -> dict:
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$status",
                "count": {"$sum": 1}
            }}
        ]
        cursor = self.collection.aggregate(pipeline)
        results = await cursor.to_list(length=50)
        stats = {r["_id"]: r["count"] for r in results}
        total = sum(stats.values())
        return {
            "total": total,
            "by_status": stats,
            "applied": stats.get("APPLIED", 0),
            "in_review": stats.get("IN_REVIEW", 0),
            "interview_scheduled": stats.get("INTERVIEW_SCHEDULED", 0),
            "offered": stats.get("OFFERED", 0),
            "rejected": stats.get("REJECTED", 0),
            "withdrawn": stats.get("WITHDRAWN", 0),
        }

    async def count_this_week(self, user_id: str) -> int:
        week_start = datetime.utcnow() - timedelta(days=7)
        return await self.collection.count_documents({
            "user_id": user_id,
            "applied_at": {"$gte": week_start}
        })

    async def get_response_rate(self, user_id: str) -> float:
        total = await self.collection.count_documents({"user_id": user_id})
        if total == 0:
            return 0.0
        responded = await self.collection.count_documents({
            "user_id": user_id,
            "status": {"$in": ["IN_REVIEW", "INTERVIEW_SCHEDULED", "OFFERED", "REJECTED"]}
        })
        return round((responded / total) * 100, 2)

    async def get_interview_rate(self, user_id: str) -> float:
        total = await self.collection.count_documents({"user_id": user_id})
        if total == 0:
            return 0.0
        interviews = await self.collection.count_documents({
            "user_id": user_id,
            "status": {"$in": ["INTERVIEW_SCHEDULED", "OFFERED"]}
        })
        return round((interviews / total) * 100, 2)
    
    async def find_needing_followup(self, cutoff_days: int = 7, limit: int = 500) -> list[dict]:
        """Sab users ke saare APPLIED applications jinhe cutoff_days se zyada
        ho gaye aur abhi tak reminder nahi gaya. Background loop ke liye."""
        cutoff = datetime.utcnow() - timedelta(days=cutoff_days)
        cursor = self.collection.find({
            "status": "APPLIED",
            "applied_at": {"$ne": None, "$lte": cutoff},
            "follow_up_sent_at": {"$exists": False},
        }).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_needing_followup_for_user(self, user_id: str, cutoff_days: int = 7) -> list[dict]:
        """Same as above but sirf ek user ke liye — manual trigger endpoint ke liye."""
        cutoff = datetime.utcnow() - timedelta(days=cutoff_days)
        cursor = self.collection.find({
            "user_id": user_id,
            "status": "APPLIED",
            "applied_at": {"$ne": None, "$lte": cutoff},
            "follow_up_sent_at": {"$exists": False},
        })
        return await cursor.to_list(length=200)

    async def mark_followup_sent(self, app_id: str) -> bool:
        if not ObjectId.is_valid(app_id):
            return False
        result = await self.collection.update_one(
            {"_id": ObjectId(app_id)},
            {"$set": {"follow_up_sent_at": datetime.utcnow()}}
        )
        return result.modified_count > 0