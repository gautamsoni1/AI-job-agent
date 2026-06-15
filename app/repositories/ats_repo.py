from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class ATSRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "ats_reports")

    async def find_by_user(self, user_id: str, limit: int = 50) -> list[dict]:
        cursor = self.collection.find(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        ).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_latest(self, user_id: str) -> dict | None:
        return await self.collection.find_one(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        )

    async def get_trend(self, user_id: str, limit: int = 20) -> list[dict]:
        cursor = self.collection.find(
            {"user_id": user_id},
            {"ats_score": 1, "created_at": 1, "job_title": 1},
            sort=[("created_at", 1)]
        ).limit(limit)
        return await cursor.to_list(length=limit)

    async def get_score_improvement(self, user_id: str) -> float:
        docs = await self.get_trend(user_id, limit=2)
        if len(docs) < 2:
            return 0.0
        return round(docs[-1].get("ats_score", 0) - docs[0].get("ats_score", 0), 2)