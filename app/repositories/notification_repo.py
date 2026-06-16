from datetime import datetime, timezone
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class NotificationRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "notifications")

    async def find_by_user(self, user_id: str, limit: int = 20, unread_only: bool = False) -> list[dict]:
        filter_ = {"user_id": user_id}
        if unread_only:
            filter_["is_read"] = False
        cursor = self.collection.find(filter_, sort=[("created_at", -1)]).limit(limit)
        return await cursor.to_list(length=limit)

    async def create_notification(self, user_id: str, title: str, message: str, type_: str = "info", action_url: str = None) -> str:
        doc = {
            "user_id": user_id,
            "title": title,
            "message": message,
            "type": type_,
            "is_read": False,
            "action_url": action_url,
            "created_at": datetime.now(timezone.utc),
        }
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def mark_read(self, notification_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(notification_id), "user_id": user_id},
            {"$set": {"is_read": True}}
        )
        return result.modified_count > 0

    async def count_unread(self, user_id: str) -> int:
        return await self.collection.count_documents({"user_id": user_id, "is_read": False})