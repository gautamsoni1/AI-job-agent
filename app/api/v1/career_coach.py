"""
Career Coach API Endpoints — Roadmap, Gap Analysis, Weekly Goals, Health Score
"""
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.schemas.career import CareerRoadmapResponse, CareerGapAnalysisResponse, WeeklyGoalResponse
from app.ai.orchestrator import AIOrchestrator
from app.ai.decision_engine import AIDecisionEngine
from app.ai.groq_client import GroqClient
from app.ai.memory import AIMemoryManager

router = APIRouter()


@router.get("/roadmap", response_model=CareerRoadmapResponse)
async def get_roadmap(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="career_coach_agent",
        task="generate_roadmap",
        user_id=str(current_user["_id"]),
        payload={},
    )
    data = result.data

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "CAREER_ROADMAP_GENERATED", "Career roadmap generated",
        {"short_term_count": len(data.get("short_term_goals", []))},
    )

    return CareerRoadmapResponse(
        short_term_goals=data.get("short_term_goals", []),
        mid_term_goals=data.get("mid_term_goals", []),
        long_term_goals=data.get("long_term_goals", []),
        recommended_skills=data.get("recommended_skills", []),
        recommended_certifications=data.get("recommended_certifications", []),
        recommended_projects=data.get("recommended_projects", []),
        summary=data.get("summary", ""),
    )


@router.get("/gap-analysis", response_model=CareerGapAnalysisResponse)
async def get_gap_analysis(
    target_role: str = Query(..., description="Target role to analyze gap for"),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="career_coach_agent",
        task="analyze_gap",
        user_id=str(current_user["_id"]),
        payload={"target_role": target_role},
    )
    data = result.data
    return CareerGapAnalysisResponse(
        target_role=data.get("target_role", target_role),
        current_level=data.get("current_level", ""),
        target_level=data.get("target_level", ""),
        skill_gaps=data.get("skill_gaps", []),
        experience_gaps=data.get("experience_gaps", []),
        education_gaps=data.get("education_gaps", []),
        time_to_ready=data.get("time_to_ready", ""),
        action_plan=data.get("action_plan", []),
    )


@router.get("/weekly-goals", response_model=WeeklyGoalResponse)
async def get_weekly_goals(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="career_coach_agent",
        task="weekly_goals",
        user_id=str(current_user["_id"]),
        payload={},
    )
    data = result.data
    return WeeklyGoalResponse(
        week_focus=data.get("week_focus", ""),
        goals=data.get("goals", []),
        daily_tasks=data.get("daily_tasks", []),
        skill_to_practice=data.get("skill_to_practice", ""),
        job_to_apply_count=data.get("job_to_apply_count", 5),
        networking_goal=data.get("networking_goal", ""),
    )


@router.get("/certifications")
async def get_recommended_certifications(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="career_coach_agent",
        task="generate_roadmap",
        user_id=str(current_user["_id"]),
        payload={},
    )
    return {"success": True, "certifications": result.data.get("recommended_certifications", [])}


@router.get("/projects")
async def get_recommended_projects(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="career_coach_agent",
        task="generate_roadmap",
        user_id=str(current_user["_id"]),
        payload={},
    )
    return {"success": True, "projects": result.data.get("recommended_projects", [])}


@router.get("/health-score")
async def get_career_health_score(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    groq_client = GroqClient()
    memory_manager = AIMemoryManager(db)
    engine = AIDecisionEngine(groq_client, memory_manager)
    health = await engine.compute_career_health(str(current_user["_id"]))

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "CAREER_HEALTH_CALCULATED",
        f"Career health score: {health.get('career_health_score', 0):.0f}/100",
        health,
    )
    return {"success": True, "data": health}


@router.get("/insights")
async def get_user_insights(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    from app.repositories.job_repo import JobRepository
    job_repo = JobRepository(db)
    recent_jobs = await job_repo.find_by_user(str(current_user["_id"]), limit=20)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="user_insight_agent",
        task="generate_insights",
        user_id=str(current_user["_id"]),
        payload={"recent_jobs": recent_jobs},
    )
    return {"success": True, "insights": result.data}


async def _log_timeline(db, user_id: str, event_type: str, title: str, metadata: dict):
    from datetime import datetime
    await db["ai_timeline"].insert_one({
        "user_id": user_id, "event_type": event_type,
        "title": title, "description": title,
        "metadata": metadata, "created_at": datetime.utcnow(),
    })