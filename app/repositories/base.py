"""
Generic Async MongoDB Repository Base Class
"""
from datetime import datetime, timezone
from typing import Optional, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
import structlog

logger = structlog.get_logger(__name__)


class BaseRepository:
    def __init__(self, db: AsyncIOMotorDatabase, collection_name: str):
        self.db = db
        self.collection = db[collection_name]
        self.collection_name = collection_name

    def _to_id(self, id_str: str) -> ObjectId:
        try:
            return ObjectId(id_str)
        except Exception:
            raise ValueError(f"Invalid ID: {id_str}")

    def _serialize(self, doc: dict) -> dict:
        if doc and "_id" in doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def get_by_id(self, id_str: str) -> Optional[dict]:
        doc = await self.collection.find_one({"_id": self._to_id(id_str)})
        return self._serialize(doc) if doc else None

    async def get_all(self, filter: dict = None, skip: int = 0, limit: int = 20, sort: list = None) -> list[dict]:
        filter = filter or {}
        cursor = self.collection.find(filter).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        docs = await cursor.to_list(length=limit)
        return [self._serialize(d) for d in docs]

    async def count(self, filter: dict = None) -> int:
        return await self.collection.count_documents(filter or {})

    async def insert(self, data: dict) -> str:
        data.pop("_id", None)
        result = await self.collection.insert_one(data)
        return str(result.inserted_id)

    async def update(self, id_str: str, update_data: dict) -> bool:
        update_data["updated_at"] = datetime.now(timezone.utc)
        result = await self.collection.update_one(
            {"_id": self._to_id(id_str)},
            {"$set": update_data}
        )
        return result.modified_count > 0

    async def delete(self, id_str: str) -> bool:
        result = await self.collection.delete_one({"_id": self._to_id(id_str)})
        return result.deleted_count > 0

    async def find_one(self, filter: dict) -> Optional[dict]:
        doc = await self.collection.find_one(filter)
        return self._serialize(doc) if doc else None

    async def find_many(self, filter: dict, skip: int = 0, limit: int = 20, sort: list = None) -> list[dict]:
        cursor = self.collection.find(filter).skip(skip).limit(limit)
        if sort:
            cursor = cursor.sort(sort)
        docs = await cursor.to_list(length=limit)
        return [self._serialize(d) for d in docs]

    async def upsert(self, filter: dict, data: dict) -> str:
        data["updated_at"] = datetime.now(timezone.utc)
        result = await self.collection.find_one_and_update(
            filter,
            {"$set": data},
            upsert=True,
            return_document=True,
        )
        return str(result["_id"])
