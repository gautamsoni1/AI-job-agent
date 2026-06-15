from datetime import datetime, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class ProfileRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "profiles")

    async def find_by_user(self, user_id: str) -> Optional[dict]:
        return await self.find_one({"user_id": user_id})

    async def upsert_for_user(self, user_id: str, data: dict) -> str:
        data["user_id"] = user_id
        data["updated_at"] = datetime.now(timezone.utc)
        return await self.upsert({"user_id": user_id}, data)