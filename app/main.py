"""
AI Job Agent Platform — FastAPI Application Factory
"""
import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings, validate_startup_config
from app.database import connect_db, disconnect_db, get_database
from app.core.exceptions import APIError
from app.core.middleware import RequestLoggingMiddleware
from app.api.v1.router import api_v1_router
from app.services.followup_service import FollowUpService

logger = structlog.get_logger(__name__)

FOLLOWUP_CHECK_INTERVAL_SECONDS = 6 * 60 * 60  # har 6 ghante


async def _followup_check_loop():
    """Background loop — applications jo APPLIED status mein 7+ din se
    padi hain unke liye reminder bhejta hai. Pure asyncio, koi naya
    dependency nahi. Pehle sleep karta hai taaki dev mein --reload ke
    har restart par DB hit na ho."""
    while True:
        await asyncio.sleep(FOLLOWUP_CHECK_INTERVAL_SECONDS)
        try:
            db = get_database()
            service = FollowUpService(db)
            await service.run_followup_check()
        except Exception as e:
            logger.warning("followup_loop_error", error=str(e))


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AI Job Agent Platform", version="1.0.0", env=settings.APP_ENV)

    # ── Validate .env before anything else ──────────────────────────────
    # Raises RuntimeError immediately if critical keys are missing/wrong.
    # The error message tells the developer exactly what to fix in .env
    # instead of a cryptic crash on the first real request.
    validate_startup_config()
    # ────────────────────────────────────────────────────────────────────

    await connect_db()
    logger.info("MongoDB connected")

    # ── Start background follow-up reminder loop ─────────────────────────
    followup_task = asyncio.create_task(_followup_check_loop())
    # ────────────────────────────────────────────────────────────────────

    yield

    # ── Stop background loop cleanly before disconnecting DB ─────────────
    followup_task.cancel()
    try:
        await followup_task
    except asyncio.CancelledError:
        pass
    # ────────────────────────────────────────────────────────────────────

    await disconnect_db()
    logger.info("MongoDB disconnected")


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Job Agent Platform",
        description="AI-Native Career Intelligence Platform powered by Groq + Mistral",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    allowed_origins = [
        settings.FRONTEND_URL,
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestLoggingMiddleware)

    app.include_router(api_v1_router, prefix="/api/v1")

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details or {},
                },
                "request_id": request.state.request_id if hasattr(request.state, "request_id") else None,
            },
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                },
            },
        )

    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "version": "1.0.0", "platform": "AI Job Agent"}

    return app


app = create_app()
