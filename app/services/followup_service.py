"""
Application Follow-Up Service — applications jo APPLIED status mein 7+ din
se padi hain unke liye ek-baar in-app notification + best-effort email
bhejta hai. Koi webhook/cron dependency nahi — pure asyncio loop (main.py
mein) ya manual endpoint se trigger hota hai.
"""
from datetime import datetime

import structlog
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.repositories.notification_repo import NotificationRepository
from app.services.email_service import EmailService

logger = structlog.get_logger()

FOLLOWUP_AFTER_DAYS = 7


class FollowUpService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.app_repo = ApplicationRepository(db)
        self.job_repo = JobRepository(db)
        self.notification_repo = NotificationRepository(db)

    async def run_followup_check(self, cutoff_days: int = FOLLOWUP_AFTER_DAYS) -> int:
        """Saare users ke stale applications check karta hai. Background
        loop se call hota hai. Safe to call repeatedly — already-reminded
        applications follow_up_sent_at ki wajah se dobara skip ho jaati hain."""
        due_apps = await self.app_repo.find_needing_followup(cutoff_days)
        created = 0
        for app in due_apps:
            try:
                await self._notify_one(app)
                created += 1
            except Exception as e:
                logger.warning("followup_notify_failed", app_id=str(app.get("_id")), error=str(e))
        if due_apps:
            logger.info("followup_check_completed", due=len(due_apps), notified=created)
        return created

    async def run_followup_check_for_user(self, user_id: str, cutoff_days: int = FOLLOWUP_AFTER_DAYS) -> int:
        """Manual on-demand trigger ke liye — sirf ek user ke applications."""
        due_apps = await self.app_repo.find_needing_followup_for_user(user_id, cutoff_days)
        created = 0
        for app in due_apps:
            try:
                await self._notify_one(app)
                created += 1
            except Exception as e:
                logger.warning("followup_notify_failed", app_id=str(app.get("_id")), error=str(e))
        return created

    async def _notify_one(self, app: dict) -> None:
        app_id = str(app["_id"])
        job = await self.job_repo.get_by_id(app.get("job_id", "")) or {}
        company = job.get("company") or "this company"
        title = job.get("title") or "this role"
        applied_at = app.get("applied_at")
        days_since = (datetime.utcnow() - applied_at).days if applied_at else FOLLOWUP_AFTER_DAYS

        await self.notification_repo.create_notification(
            user_id=app["user_id"],
            title="Time to follow up",
            message=f"Aaj {days_since} din ho gaye — {title} at {company} ke liye follow up karo.",
            type_="warning",
            action_url=f"/applications/{app_id}",
        )

        # Best-effort — EmailService apne andar failures handle karta hai,
        # isliye SMTP missing/broken hone par bhi ye line kabhi raise nahi karegi.
        user_doc = await self.db["users"].find_one({"_id": ObjectId(app["user_id"])})
        if user_doc and user_doc.get("email"):
            email_service = EmailService()
            await email_service.send_followup_reminder_email(
                email=user_doc["email"],
                first_name=user_doc.get("first_name", ""),
                company=company,
                role=title,
                days_since=days_since,
            )

        await self.app_repo.mark_followup_sent(app_id)