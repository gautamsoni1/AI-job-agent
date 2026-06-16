"""
Cover Letter API Endpoints — Generate, List, Download
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
import os

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError
from app.repositories.cover_letter_repo import CoverLetterRepository
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.cover_letter import GenerateCoverLetterRequest, CoverLetterResponse
from app.ai.orchestrator import AIOrchestrator

router = APIRouter()


@router.post("/generate", response_model=CoverLetterResponse, status_code=201)
async def generate_cover_letter(
    body: GenerateCoverLetterRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    job_repo = JobRepository(db)
    resume_repo = ResumeRepository(db)

    job = await job_repo.get_by_id(body.job_id)
    if not job:
        raise NotFoundError("Job", body.job_id)

    resume = await resume_repo.get_by_id(body.resume_id)
    if not resume or resume.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Resume", body.resume_id)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="cover_letter_agent",
        task="generate",
        user_id=str(current_user["_id"]),
        payload={
            "resume_text": resume.get("raw_text", ""),
            "job": job,
            "company_name": job.get("company", ""),
            "tone": body.tone,
        },
    )

    data = result.data
    now = datetime.now(timezone.utc)
    cl_doc = {
        "user_id": str(current_user["_id"]),
        "job_id": body.job_id,
        "resume_id": body.resume_id,
        "company_name": job.get("company", ""),
        "role_title": job.get("title", ""),
        "tone": body.tone,
        "content": data.get("full_text", ""),
        "version": 1,
        "created_at": now,
    }

    cl_repo = CoverLetterRepository(db)
    cl_id = await cl_repo.insert(cl_doc)

    background_tasks.add_task(
        _log_timeline, db, str(current_user["_id"]),
        "COVER_LETTER_GENERATED",
        f"Cover letter generated for {job.get('title')} at {job.get('company')}",
        {"cl_id": cl_id, "job_id": body.job_id},
    )

    return CoverLetterResponse(
        id=cl_id,
        company_name=cl_doc["company_name"],
        role_title=cl_doc["role_title"],
        tone=cl_doc["tone"],
        content=cl_doc["content"],
        file_path=None,
        version=1,
        created_at=now,
    )


@router.get("/")
async def list_cover_letters(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cl_repo = CoverLetterRepository(db)
    letters = await cl_repo.find_by_user(str(current_user["_id"]))
    result = []
    for l in letters:
        l["id"] = str(l.pop("_id", ""))
        result.append(l)
    return {"success": True, "cover_letters": result}


@router.get("/{cl_id}", response_model=CoverLetterResponse)
async def get_cover_letter(
    cl_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cl_repo = CoverLetterRepository(db)
    letter = await cl_repo.get_by_id(cl_id)
    if not letter or letter.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Cover Letter", cl_id)
    return CoverLetterResponse(
        id=str(letter["_id"]),
        company_name=letter.get("company_name", ""),
        role_title=letter.get("role_title", ""),
        tone=letter.get("tone", "professional"),
        content=letter.get("content", ""),
        file_path=letter.get("file_path"),
        version=letter.get("version", 1),
        created_at=letter.get("created_at", datetime.now(timezone.utc)),
    )


@router.get("/{cl_id}/download")
async def download_cover_letter(
    cl_id: str,
    format: str = "txt",
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    cl_repo = CoverLetterRepository(db)
    letter = await cl_repo.get_by_id(cl_id)
    if not letter or letter.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Cover Letter", cl_id)

    content = letter.get("content", "")
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        tmp_path = f.name

    filename = f"cover_letter_{letter.get('company_name', 'company').replace(' ', '_')}.txt"
    return FileResponse(path=tmp_path, filename=filename, media_type="text/plain")


async def _log_timeline(db, user_id: str, event_type: str, title: str, metadata: dict):
    from datetime import datetime
    await db["ai_timeline"].insert_one({
        "user_id": user_id, "event_type": event_type,
        "title": title, "description": title,
        "metadata": metadata, "created_at": datetime.utcnow(),
    })