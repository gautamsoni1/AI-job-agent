import re
from fastapi import logger
import structlog
from datetime import datetime
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import BulkWriteError
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "jobs")

    async def find_by_user(self, user_id: str, skip: int = 0, limit: int = 50) -> list[dict]:
        pipeline = [
            {"$match": {"user_id": user_id, "is_deleted": {"$ne": True}}},
            {"$addFields": {
                "_days_old": {
                    "$cond": [
                        {"$ifNull": ["$posted_date", False]},
                        {"$divide": [{"$subtract": ["$$NOW", "$posted_date"]}, 1000 * 60 * 60 * 24]},
                        9999,
                    ]
                }
            }},
            {"$addFields": {
                "_recency_bucket": {
                    "$switch": {
                        "branches": [
                            {"case": {"$lte": ["$_days_old", 7]}, "then": 1},
                            {"case": {"$lte": ["$_days_old", 14]}, "then": 2},
                            {"case": {"$lte": ["$_days_old", 21]}, "then": 3},
                            {"case": {"$lte": ["$_days_old", 28]}, "then": 4},
                        ],
                        "default": 5,
                    }
                }
            }},
            {"$sort": {"_recency_bucket": 1, "ai_score": -1, "created_at": -1}},
            {"$skip": skip},
            {"$limit": limit},
        ]
        return await self.collection.aggregate(pipeline).to_list(length=limit)

    async def find_saved_by_user(self, user_id: str) -> list[dict]:
        pipeline = [
            {"$match": {"user_id": user_id, "is_saved": True, "is_deleted": {"$ne": True}}},
            {"$addFields": {
                "_days_old": {
                    "$cond": [
                        {"$ifNull": ["$posted_date", False]},
                        {"$divide": [{"$subtract": ["$$NOW", "$posted_date"]}, 1000 * 60 * 60 * 24]},
                        9999,
                    ]
                }
            }},
            {"$addFields": {
                "_recency_bucket": {
                    "$switch": {
                        "branches": [
                            {"case": {"$lte": ["$_days_old", 7]}, "then": 1},
                            {"case": {"$lte": ["$_days_old", 14]}, "then": 2},
                            {"case": {"$lte": ["$_days_old", 21]}, "then": 3},
                            {"case": {"$lte": ["$_days_old", 28]}, "then": 4},
                        ],
                        "default": 5,
                    }
                }
            }},
            {"$sort": {"_recency_bucket": 1, "saved_at": -1}},
        ]
        return await self.collection.aggregate(pipeline).to_list(length=100)

    async def find_top_matches(self, user_id: str, limit: int = 10) -> list[dict]:
        pipeline = [
            {"$match": {"user_id": user_id, "match_score": {"$exists": True}, "is_deleted": {"$ne": True}}},
            {"$addFields": {
                "_days_old": {
                    "$cond": [
                        {"$ifNull": ["$posted_date", False]},
                        {"$divide": [{"$subtract": ["$$NOW", "$posted_date"]}, 1000 * 60 * 60 * 24]},
                        9999,
                    ]
                }
            }},
            {"$addFields": {
                "_recency_bucket": {
                    "$switch": {
                        "branches": [
                            {"case": {"$lte": ["$_days_old", 7]}, "then": 1},
                            {"case": {"$lte": ["$_days_old", 14]}, "then": 2},
                            {"case": {"$lte": ["$_days_old", 21]}, "then": 3},
                            {"case": {"$lte": ["$_days_old", 28]}, "then": 4},
                        ],
                        "default": 5,
                    }
                }
            }},
            {"$sort": {"_recency_bucket": 1, "match_score": -1}},
            {"$limit": limit},
        ]
        return await self.collection.aggregate(pipeline).to_list(length=limit)

    async def check_duplicate(self, user_id: str, apply_link: str) -> Optional[dict]:
        return await self.collection.find_one(
            {"user_id": user_id, "apply_link": apply_link}
        )

    async def save_job(self, job_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(job_id), "user_id": user_id},
            {"$set": {"is_saved": True, "saved_at": datetime.utcnow(), "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def unsave_job(self, job_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(job_id), "user_id": user_id},
            {"$set": {"is_saved": False, "updated_at": datetime.utcnow()}, "$unset": {"saved_at": ""}}
        )
        return result.modified_count > 0

    async def update_scout_report(self, job_id: str, scout_report: dict) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"scout_report": scout_report, "ai_score": scout_report.get("relevance_score", 0), "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def update_match_score(self, job_id: str, match_score: float, match_report: dict) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": {"match_score": match_score, "match_report": match_report, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def bulk_insert_jobs(self, jobs: list[dict]) -> list[str]:
        if not jobs:
            return []
        result = await self.collection.insert_many(jobs, ordered=False)
        return [str(id_) for id_ in result.inserted_ids]

    async def count_by_user(self, user_id: str) -> int:
        return await self.collection.count_documents({"user_id": user_id, "is_deleted": {"$ne": True}})

    async def get_all_for_admin(self, skip: int = 0, limit: int = 100) -> list[dict]:
        cursor = self.collection.find({}, sort=[("created_at", -1)]).skip(skip).limit(limit)
        return await cursor.to_list(length=limit)
    
    async def find_all_user_job_keys(self, user_id: str) -> set:
        """
        Cross-run deduplication ke liye user ke saare existing jobs ke
        normalized keys return karta hai — title+company+location tuple
        AND apply_link string, dono forms mein.
        """
        cursor = self.collection.find(
            {"user_id": user_id, "is_deleted": {"$ne": True}},
            {"title": 1, "company": 1, "location": 1, "apply_link": 1}
        )
    
        docs = await cursor.to_list(length=5000)
    
        keys: set = set()
    
        for doc in docs:
            keys.add((
                (doc.get("title") or "").strip().lower(),
                (doc.get("company") or "").strip().lower(),
                (doc.get("location") or "").strip().lower(),
            ))
    
            link = (doc.get("apply_link") or "").strip()
            if link:
                keys.add(link)
    
        return keys
    
    async def find_existing_similar(self, user_id: str, title: str, company: str, apply_link: str = "") -> Optional[dict]:
        """Catches duplicates even when apply_link differs or is missing —
        same title + company for the same user counts as the same job."""
        filters = []
        if apply_link:
            filters.append({"apply_link": apply_link})
        if title and company:
            filters.append({
                "title": {"$regex": f"^{re.escape(title.strip())}$", "$options": "i"},
                "company": {"$regex": f"^{re.escape(company.strip())}$", "$options": "i"},
            })
        if not filters:
            return None
        return await self.collection.find_one({
            "user_id": user_id, "is_deleted": {"$ne": True}, "$or": filters,
        })
    logger = structlog.get_logger()

    async def bulk_insert_jobs(self, jobs: list[dict]) -> list[str]:
        if not jobs:
            return []
        try:
            result = await self.collection.insert_many(jobs, ordered=False)
            return [str(id_) for id_ in result.inserted_ids]
        except BulkWriteError as e:
            failed_indices = {err["index"] for err in e.details.get("writeErrors", [])}
            inserted_ids = [
                str(job["_id"])
                for idx, job in enumerate(jobs)
                if idx not in failed_indices and "_id" in job
            ]
            logger.warning(
                "bulk_insert_partial_failure",
                attempted=len(jobs),
                inserted=len(inserted_ids),
                failed=len(failed_indices),
            )
            return inserted_ids