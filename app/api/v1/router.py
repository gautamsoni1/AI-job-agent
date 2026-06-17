"""
Master API v1 Router — registers all sub-routers.
"""
from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.profile import router as profile_router
from app.api.v1.resume import router as resume_router
from app.api.v1.ats import router as ats_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.matching import router as matching_router
from app.api.v1.applications import router as applications_router
from app.api.v1.cover_letter import router as cover_letter_router
from app.api.v1.career_coach import router as career_coach_router
from app.api.v1.interview_prep import router as interview_prep_router
from app.api.v1.market_intel import router as market_intel_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.ai_timeline import router as ai_timeline_router
from app.api.v1.admin import router as admin_router
from app.api.v1.pipeline import router as pipeline_router


api_v1_router = APIRouter()

api_v1_router.include_router(auth_router, prefix="/auth", tags=["Auth"])
api_v1_router.include_router(profile_router, prefix="/profile", tags=["Profile"])
api_v1_router.include_router(resume_router, prefix="/resume", tags=["Resume"])
api_v1_router.include_router(ats_router, prefix="/ats", tags=["ATS"])
api_v1_router.include_router(jobs_router, prefix="/jobs", tags=["Jobs"])
api_v1_router.include_router(matching_router, prefix="/matching", tags=["Matching"])
api_v1_router.include_router(applications_router, prefix="/applications", tags=["Applications"])
api_v1_router.include_router(cover_letter_router, prefix="/cover-letter", tags=["Cover Letter"])
api_v1_router.include_router(career_coach_router, prefix="/career", tags=["Career Coach"])
api_v1_router.include_router(interview_prep_router, prefix="/interview", tags=["Interview"])
api_v1_router.include_router(market_intel_router, prefix="/market", tags=["Market Intel"])
api_v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["Dashboard"])
api_v1_router.include_router(ai_timeline_router, prefix="/timeline", tags=["AI Timeline"])
api_v1_router.include_router(admin_router, prefix="/admin", tags=["Admin"])
api_v1_router.include_router(pipeline_router, prefix="/pipeline", tags=["Pipeline"])