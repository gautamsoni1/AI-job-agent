"""
Market Intelligence API Endpoints — Trends, Skills, Salaries, Companies
"""
from fastapi import APIRouter, Depends, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.repositories.job_repo import JobRepository
from app.ai.orchestrator import AIOrchestrator

router = APIRouter()


@router.get("/trends")
async def get_market_trends(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    job_repo = JobRepository(db)
    jobs = await job_repo.find_by_user(str(current_user["_id"]), limit=50)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="market_intel_agent",
        task="analyze_market",
        user_id=str(current_user["_id"]),
        payload={"jobs": jobs},
    )

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "MARKET_ANALYSIS_RUN", "Market trend analysis completed",
        {"job_count": len(jobs)},
    )
    return {"success": True, "data": result.data}


@router.get("/skills")
async def get_trending_skills(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    job_repo = JobRepository(db)
    jobs = await job_repo.find_by_user(str(current_user["_id"]), limit=50)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="market_intel_agent",
        task="analyze_market",
        user_id=str(current_user["_id"]),
        payload={"jobs": jobs},
    )
    return {"success": True, "skills": result.data.get("top_demanded_skills", [])}


@router.get("/salaries")
async def get_salary_ranges(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    job_repo = JobRepository(db)
    jobs = await job_repo.find_by_user(str(current_user["_id"]), limit=50)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="market_intel_agent",
        task="analyze_market",
        user_id=str(current_user["_id"]),
        payload={"jobs": jobs},
    )
    return {"success": True, "salary_ranges": result.data.get("salary_ranges", [])}


@router.get("/companies")
async def get_top_hiring_companies(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    job_repo = JobRepository(db)
    jobs = await job_repo.find_by_user(str(current_user["_id"]), limit=50)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="market_intel_agent",
        task="analyze_market",
        user_id=str(current_user["_id"]),
        payload={"jobs": jobs},
    )
    return {"success": True, "companies": result.data.get("top_hiring_companies", [])}


@router.get("/fit-score")
async def get_market_fit_score(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    job_repo = JobRepository(db)
    jobs = await job_repo.find_by_user(str(current_user["_id"]), limit=30)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="market_intel_agent",
        task="analyze_market",
        user_id=str(current_user["_id"]),
        payload={"jobs": jobs},
    )
    return {
        "success": True,
        "market_fit_score": result.data.get("user_market_fit_score", 0.0),
        "market_summary": result.data.get("market_summary", ""),
    }


async def _log_timeline(db, user_id: str, event_type: str, title: str, metadata: dict):
    from datetime import datetime
    await db["ai_timeline"].insert_one({
        "user_id": user_id, "event_type": event_type,
        "title": title, "description": title,
        "metadata": metadata, "created_at": datetime.utcnow(),
    })