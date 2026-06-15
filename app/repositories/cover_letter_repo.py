from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class CoverLetterRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "cover_letters")

    async def find_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
        cursor = self.collection.find(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        ).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_by_job(self, user_id: str, job_id: str) -> Optional[dict]:
        return await self.find_one({"user_id": user_id, "job_id": job_id})