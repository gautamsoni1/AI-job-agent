from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.base import BaseRepository


class PipelineRunRepository(BaseRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        super().__init__(db, "pipeline_runs")

    async def find_by_user(self, user_id: str, limit: int = 20) -> list[dict]:
        cursor = self.collection.find(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        ).limit(limit)
        return await cursor.to_list(length=limit)