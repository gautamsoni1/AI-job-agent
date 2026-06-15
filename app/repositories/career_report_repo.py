from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class CareerReportRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "career_reports")

    async def get_latest(self, user_id: str, report_type: str) -> Optional[dict]:
        return await self.collection.find_one(
            {"user_id": user_id, "report_type": report_type},
            sort=[("created_at", -1)]
        )

    async def find_by_user(self, user_id: str, report_type: Optional[str] = None, limit: int = 20) -> list[dict]:
        filter_ = {"user_id": user_id}
        if report_type:
            filter_["report_type"] = report_type
        cursor = self.collection.find(filter_, sort=[("created_at", -1)]).limit(limit)
        return await cursor.to_list(length=limit)