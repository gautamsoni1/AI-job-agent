from datetime import datetime
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class TimelineRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "ai_timeline")

    async def find_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
        cursor = self.collection.find(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        ).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def find_by_event_type(self, user_id: str, event_type: str, limit: int = 20) -> list[dict]:
        cursor = self.collection.find(
            {"user_id": user_id, "event_type": event_type},
            sort=[("created_at", -1)]
        ).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_today(self, user_id: str) -> int:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        return await self.collection.count_documents({
            "user_id": user_id,
            "created_at": {"$gte": today}
        })

    async def log_event(self, user_id: str, event_type: str, title: str, description: str, metadata: dict = None) -> str:
        doc = {
            "user_id": user_id,
            "event_type": event_type,
            "title": title,
            "description": description,
            "metadata": metadata or {},
            "created_at": datetime.utcnow()
        }
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)