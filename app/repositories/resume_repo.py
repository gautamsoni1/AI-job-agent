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
        if not ObjectId.is_valid(resume_id):
            return False
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
        if not ObjectId.is_valid(resume_id):
            return False
        result = await self.collection.update_one(
            {"_id": ObjectId(resume_id), "user_id": user_id},
            {"$set": {"is_deleted": True, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def save_version(self, version_data: dict) -> str:
        result = await self.db["resume_versions"].insert_one(version_data)
        return str(result.inserted_id)

    async def get_versions(self, resume_id: str, user_id: str) -> list[dict]:
        if not ObjectId.is_valid(resume_id):
            return []
        related_ids = {resume_id}
        related_resumes = []
        resume = await self.collection.find_one({"_id": ObjectId(resume_id), "user_id": user_id})
        if resume:
            parent_id = resume.get("parent_resume_id")
            root_id = parent_id or resume_id
            related_ids.add(root_id)
            cursor = self.collection.find(
                {
                    "user_id": user_id,
                    "$or": [
                        {"_id": ObjectId(root_id)} if ObjectId.is_valid(root_id) else {"_id": ObjectId(resume_id)},
                        {"parent_resume_id": root_id},
                    ],
                    "is_deleted": {"$ne": True},
                }
            )
            related_resumes = await cursor.to_list(length=100)
            related_ids.update(str(doc["_id"]) for doc in related_resumes)

        cursor = self.db["resume_versions"].find(
            {
                "user_id": user_id,
                "$or": [
                    {"resume_id": {"$in": list(related_ids)}},
                    {"root_resume_id": {"$in": list(related_ids)}},
                ],
            },
            sort=[("created_at", -1)]
        )
        docs = await cursor.to_list(length=50)
        if not docs and related_resumes:
            return [
                {
                    "id": str(doc["_id"]),
                    "resume_id": str(doc["_id"]),
                    "root_resume_id": doc.get("parent_resume_id") or str(doc["_id"]),
                    "parent_resume_id": doc.get("parent_resume_id"),
                    "user_id": doc.get("user_id"),
                    "version_number": doc.get("version_number", 1),
                    "label": doc.get("label") or ("Original Upload" if not doc.get("parent_resume_id") else "ATS Optimized"),
                    "filename": doc.get("filename", ""),
                    "file_path": doc.get("generated_file_path") or doc.get("file_path", ""),
                    "file_type": doc.get("generated_file_type") or doc.get("file_type", ""),
                    "raw_text": doc.get("raw_text", ""),
                    "parsed_sections": doc.get("parsed_sections", {}),
                    "skills_extracted": doc.get("skills_extracted", []),
                    "source": "ai_rewrite" if doc.get("parent_resume_id") else "upload",
                    "changes_made": [],
                    "target_role": None,
                    "ats_target_score": doc.get("ats_target_score"),
                    "projected_ats_score": doc.get("projected_ats_score") or doc.get("latest_ats_score"),
                    "projected_pass_rate": doc.get("projected_pass_rate"),
                    "improvement_score": doc.get("improvement_score"),
                    "download_url": f"/api/v1/resume/{doc['_id']}/download",
                    "created_at": doc.get("created_at"),
                }
                for doc in sorted(
                    related_resumes,
                    key=lambda item: item.get("version_number", 1),
                    reverse=True,
                )
            ]
        return [self._serialize(doc) for doc in docs]

    async def update_parsed_data(self, resume_id: str, parsed_data: dict) -> bool:
        if not ObjectId.is_valid(resume_id):
            return False
        result = await self.collection.update_one(
            {"_id": ObjectId(resume_id)},
            {"$set": {"parsed_data": parsed_data, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    async def update_file_path(self, resume_id: str, file_path: str, file_type: str) -> bool:
        if not ObjectId.is_valid(resume_id):
            return False
        result = await self.collection.update_one(
            {"_id": ObjectId(resume_id)},
            {"$set": {"generated_file_path": file_path, "generated_file_type": file_type, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0
