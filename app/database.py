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
    await db.users.create_index("email", unique=True)
    await db.users.create_index("verification_token")
    await db.users.create_index("reset_token")
    await db.profiles.create_index("user_id", unique=True)
    await db.resumes.create_index("user_id")
    await db.resumes.create_index([("user_id", 1), ("is_active", 1)])
    await db.resume_versions.create_index([("resume_id", 1), ("created_at", -1)])
    await db.resume_versions.create_index("user_id")

    # jobs — old global "unique+sparse" index on apply_link was the crash
    # cause: sparse still indexes "" values, and the constraint was global
    # across all users instead of per-user. Drop it and replace with a
    # scoped, partial index that only enforces uniqueness on real links.
    existing_indexes = await db.jobs.index_information()
    if "apply_link_1" in existing_indexes:
        await db.jobs.drop_index("apply_link_1")
    await db.jobs.create_index(
        [("user_id", 1), ("apply_link", 1)],
        unique=True,
        partialFilterExpression={"apply_link": {"$gt": ""}},
        name="user_apply_link_unique",
    )
    await db.jobs.create_index([("title", "text"), ("company", "text")])
    await db.jobs.create_index([("user_id", 1), ("created_at", -1)])
    await db.jobs.create_index([("user_id", 1), ("is_saved", 1)])
    await db.jobs.create_index([("user_id", 1), ("match_score", -1)])
    await db.job_matches.create_index([("user_id", 1), ("job_id", 1)])
    await db.applications.create_index([("user_id", 1), ("job_id", 1)])
    await db.applications.create_index([("user_id", 1), ("status", 1)])
    await db.ats_reports.create_index([("user_id", 1), ("created_at", -1)])
    await db.cover_letters.create_index([("user_id", 1), ("created_at", -1)])
    await db.career_reports.create_index([("user_id", 1), ("report_type", 1), ("created_at", -1)])
    await db.ai_timeline.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("is_read", 1)])
    await db.audit_logs.create_index([("user_id", 1), ("created_at", -1)])
    await db.agent_results.create_index([("user_id", 1), ("created_at", -1)])
    await db.preference_signals.create_index([("user_id", 1), ("recorded_at", -1)])
    await db.pipeline_runs.create_index([("user_id", 1), ("created_at", -1)])
    logger.info("MongoDB indexes created")