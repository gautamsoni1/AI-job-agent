from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "resumes")

    async def find_by_user(self, user_id: str) -> list[dict]:
        cursor = self.collection.find(
            {"user_id": user_id, "is_deleted": {"$ne": True}},
            sort=[("created_at", -1)]
        )
        return await cursor.to_list(length=100)

    async def find_active_by_user(self, user_id: str) -> Optional[dict]:
        return await self.collection.find_one(
            {"user_id": user_id, "is_active": True, "is_deleted": {"$ne": True}}
        )

    async def set_active(self, user_id: str, resume_id: str) -> bool:
        await self.collection.update_many(
            {"user_id": user_id},
            {"$set": {"is_active": False, "updated_at": datetime.utcnow()}}
        )
        result = await self.collection.update_one(
            {"_id": ObjectId(resume_id), "user_id": user_id},
            {"$set": {"is_active": True, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def soft_delete(self, resume_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(resume_id), "user_id": user_id},
            {"$set": {"is_deleted": True, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def save_version(self, version_data: dict) -> str:
        result = await self.db["resume_versions"].insert_one(version_data)
        return str(result.inserted_id)

    async def get_versions(self, resume_id: str, user_id: str) -> list[dict]:
        cursor = self.db["resume_versions"].find(
            {"resume_id": resume_id, "user_id": user_id},
            sort=[("created_at", -1)]
        )
        return await cursor.to_list(length=50)

    async def update_parsed_data(self, resume_id: str, parsed_data: dict) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(resume_id)},
            {"$set": {"parsed_data": parsed_data, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def update_file_path(self, resume_id: str, file_path: str, file_type: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(resume_id)},
            {"$set": {"generated_file_path": file_path, "generated_file_type": file_type, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0