from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "users")

    async def find_by_email(self, email: str) -> Optional[dict]:
        return await self.collection.find_one({"email": email.lower()})

    async def find_by_verification_token(self, token: str) -> Optional[dict]:
        return await self.collection.find_one({"verification_token": token})

    async def find_by_reset_token(self, token: str) -> Optional[dict]:
        return await self.collection.find_one({
            "reset_token": token,
            "reset_token_expires": {"$gt": datetime.utcnow()}
        })

    async def verify_email(self, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"is_verified": True, "verification_token": None, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def set_reset_token(self, user_id: str, token: str, expires: datetime) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"reset_token": token, "reset_token_expires": expires, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def clear_reset_token(self, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"reset_token": "", "reset_token_expires": ""}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def update_last_login(self, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"last_login": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def update_password(self, user_id: str, hashed_password: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"hashed_password": hashed_password, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def store_refresh_token(self, user_id: str, token: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$addToSet": {"refresh_tokens": token}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def revoke_refresh_token(self, user_id: str, token: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$pull": {"refresh_tokens": token}, "$set": {"updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def is_refresh_token_valid(self, user_id: str, token: str) -> bool:
        doc = await self.collection.find_one(
            {"_id": ObjectId(user_id), "refresh_tokens": token}
        )
        return doc is not None

    async def count_active_users(self) -> int:
        return await self.collection.count_documents({"is_active": True})