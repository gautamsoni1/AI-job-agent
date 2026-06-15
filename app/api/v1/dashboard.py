"""
Dashboard API — Single-call aggregation of all user career data
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.repositories.application_repo import ApplicationRepository
from app.repositories.job_repo import JobRepository
from app.repositories.ats_repo import ATSRepository
from app.schemas.dashboard import DashboardResponse, DashboardScores
from app.ai.decision_engine import AIDecisionEngine
from app.ai.groq_client import GroqClient
from app.ai.memory import AIMemoryManager

router = APIRouter()


@router.get("/", response_model=DashboardResponse)
async def get_dashboard(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    user_id = str(current_user["_id"])

    groq_client = GroqClient()
    memory_manager = AIMemoryManager(db)
    engine = AIDecisionEngine(groq_client, memory_manager)
    health = await engine.compute_career_health(user_id)

    app_repo = ApplicationRepository(db)
    job_repo = JobRepository(db)
    ats_repo = ATSRepository(db)

    stats = await app_repo.get_stats(user_id)
    apps_this_week = await app_repo.count_this_week(user_id)
    recent_apps = await app_repo.find_by_user(user_id, limit=5)
    top_jobs = await job_repo.find_top_matches(user_id, limit=5)
    ats_trend = await ats_repo.get_trend(user_id, limit=10)

    # Notifications
    notifs_cursor = db["notifications"].find(
        {"user_id": user_id}, sort=[("created_at", -1)]
    ).limit(10)
    notifs = await notifs_cursor.to_list(length=10)
    for n in notifs:
        n["_id"] = str(n["_id"])

    # Timeline
    timeline_cursor = db["ai_timeline"].find(
        {"user_id": user_id}, sort=[("created_at", -1)]
    ).limit(10)
    timeline = await timeline_cursor.to_list(length=10)
    for t in timeline:
        t["_id"] = str(t["_id"])

    # Top missing skills — from ATS reports
    missing_skills: list[str] = []
    all_ats = await ats_repo.find_by_user(user_id, limit=5)
    skill_counter: dict = {}
    for r in all_ats:
        for kw in r.get("missing_keywords", []):
            skill_counter[kw] = skill_counter.get(kw, 0) + 1
    missing_skills = sorted(skill_counter, key=skill_counter.get, reverse=True)[:10]  # type: ignore

    # Serialize apps and jobs
    for a in recent_apps:
        a["_id"] = str(a["_id"])
    for j in top_jobs:
        j["_id"] = str(j["_id"])

    scores = DashboardScores(
        career_health_score=health.get("career_health_score", 0),
        resume_strength_score=health.get("resume_strength_score", 0),
        application_success_rate=health.get("application_success_rate", 0),
        ats_improvement_trend=health.get("ats_improvement_trend", 0),
        interview_conversion_rate=health.get("interview_conversion_rate", 0),
        market_readiness_score=health.get("market_readiness_score", 0),
        job_search_progress_score=health.get("job_search_progress_score", 0),
        top_missing_skills=missing_skills,
        weekly_application_goal=5,
        applications_this_week=apps_this_week,
    )

    return DashboardResponse(
        scores=scores,
        recent_applications=recent_apps,
        top_opportunities=top_jobs,
        recent_timeline=timeline,
        ats_trend=[
            {
                "_id": str(r.get("_id", "")),
                "ats_score": r.get("ats_score", 0),
                "created_at": str(r.get("created_at", "")),
            }
            for r in ats_trend
        ],
        notifications=notifs,
    )