"""
MongoDB Motor Async Connection Manager
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings
import structlog

logger = structlog.get_logger(__name__)

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def connect_db():
    global _client, _database
    _client = AsyncIOMotorClient(settings.MONGODB_URI)
    _database = _client[settings.MONGODB_DB_NAME]
    # Create indexes
    await _create_indexes()
    logger.info("MongoDB connected", db=settings.MONGODB_DB_NAME)


async def disconnect_db():
    global _client
    if _client:
        _client.close()
        logger.info("MongoDB disconnected")


def get_database() -> AsyncIOMotorDatabase:
    if _database is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return _database


async def _create_indexes():
    db = get_database()
    # users
    await db.users.create_index("email", unique=True)
    await db.users.create_index("verification_token")
    # resumes
    await db.resumes.create_index("user_id")
    # jobs
    await db.jobs.create_index("apply_link", unique=True, sparse=True)
    await db.jobs.create_index([("title", "text"), ("company", "text")])
    # applications
    await db.applications.create_index([("user_id", 1), ("job_id", 1)])
    # ats_reports
    await db.ats_reports.create_index([("user_id", 1), ("created_at", -1)])
    # ai_timeline
    await db.ai_timeline.create_index([("user_id", 1), ("created_at", -1)])
    logger.info("MongoDB indexes created")