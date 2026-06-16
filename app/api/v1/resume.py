"""
Resume API Endpoints — Upload, Parse, Analyze, Optimize, Download
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError, ResumeParseError, ValidationError
from app.repositories.resume_repo import ResumeRepository
from app.services.storage_service import StorageService
from app.services.resume_parser_service import ResumeParserService
from app.schemas.resume import ResumeUploadResponse, ResumeListItem, ResumeAnalysisResponse, ResumeOptimizeRequest, ResumeOptimizeResponse
from app.ai.orchestrator import AIOrchestrator
from app.database import get_database

router = APIRouter()


def get_orchestrator(db: AsyncIOMotorDatabase = Depends(get_db)) -> AIOrchestrator:
    return AIOrchestrator(db)


@router.post("/upload", response_model=ResumeUploadResponse, status_code=201)
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    if file.content_type not in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"):
        raise ValidationError("Only PDF and DOCX files are allowed.")

    file_bytes = await file.read()
    storage = StorageService()
    try:
        file_meta = await storage.save_resume(file_bytes, file.filename or "resume", str(current_user["_id"]))
    except ValueError as e:
        raise ValidationError(str(e))

    parser = ResumeParserService()
    try:
        parsed = await parser.parse(file_meta["file_path"], file_meta["file_type"])
    except Exception as e:
        raise ResumeParseError(str(e))

    repo = ResumeRepository(db)
    existing = await repo.find_by_user(str(current_user["_id"]))
    version_number = len(existing) + 1

    resume_doc = {
        "user_id": str(current_user["_id"]),
        "filename": file.filename,
        "file_path": file_meta["file_path"],
        "file_type": file_meta["file_type"],
        "file_size": file_meta["size_bytes"],
        "raw_text": parsed.get("raw_text", ""),
        "parsed_sections": parsed.get("sections", {}),
        "skills_extracted": parsed.get("skills_found", []),
        "experience_years": None,
        "latest_title": None,
        "is_active": True,
        "version_number": version_number,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }

    # Deactivate previous active resume
    await db["resumes"].update_many(
        {"user_id": str(current_user["_id"])},
        {"$set": {"is_active": False}}
    )

    resume_id = await repo.insert(resume_doc)

    # Update user skills
    if parsed.get("skills_found"):
        await db["users"].update_one(
            {"_id": current_user["_id"]},
            {"$addToSet": {"skills": {"$each": parsed["skills_found"]}}}
        )

    # Log timeline event in background
    background_tasks.add_task(
        _log_timeline,
        db,
        str(current_user["_id"]),
        "RESUME_UPLOADED",
        f"Resume uploaded: {file.filename}",
        {"resume_id": resume_id, "version": version_number},
    )

    return ResumeUploadResponse(
        id=resume_id,
        filename=file.filename or "",
        file_type=file_meta["file_type"],
        file_size=file_meta["size_bytes"],
        skills_extracted=parsed.get("skills_found", []),
        experience_years=None,
        latest_title=None,
        version_number=version_number,
        created_at=datetime.now(timezone.utc),
    )


@router.get("/", response_model=list[ResumeListItem])
async def list_resumes(
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = ResumeRepository(db)
    resumes = await repo.find_by_user(str(current_user["_id"]))
    return [
        ResumeListItem(
            id=str(r["_id"]),
            filename=r.get("filename", ""),
            file_type=r.get("file_type", ""),
            label=r.get("label"),
            version_number=r.get("version_number", 1),
            skills_extracted=r.get("skills_extracted", []),
            is_active=r.get("is_active", False),
            created_at=r.get("created_at", datetime.now(timezone.utc)),
        )
        for r in resumes
    ]


@router.get("/{resume_id}")
async def get_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume or resume.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Resume", resume_id)
    resume.pop("raw_text", None)
    return {"success": True, "data": resume}


@router.delete("/{resume_id}")
async def delete_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = ResumeRepository(db)
    ok = await repo.soft_delete(resume_id, str(current_user["_id"]))
    if not ok:
        raise NotFoundError("Resume", resume_id)
    return {"success": True, "message": "Resume deleted."}


@router.post("/{resume_id}/analyze", response_model=ResumeAnalysisResponse)
async def analyze_resume(
    resume_id: str,
    target_role: str = "",
    background_tasks: BackgroundTasks = BackgroundTasks(),
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume or resume.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Resume", resume_id)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="resume_agent",
        task="analyze",
        user_id=str(current_user["_id"]),
        payload={"resume_text": resume.get("raw_text", ""), "target_role": target_role},
    )

    background_tasks.add_task(
        _log_timeline,
        db,
        str(current_user["_id"]),
        "RESUME_ANALYZED",
        f"Resume analyzed for: {target_role or 'General'}",
        {"resume_id": resume_id},
    )

    return ResumeAnalysisResponse(
        resume_id=resume_id,
        analysis=result.data.get("analysis", {}),
        strengths=result.data.get("strengths", []),
        weaknesses=result.data.get("weaknesses", []),
        improvement_suggestions=result.data.get("improvement_suggestions", []),
        target_roles_fit=result.data.get("target_roles_fit", {}),
        overall_score=result.data.get("overall_score", 0.0),
    )


@router.post("/{resume_id}/optimize", response_model=ResumeOptimizeResponse)
async def optimize_resume(
    resume_id: str,
    body: ResumeOptimizeRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume or resume.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Resume", resume_id)

    orchestrator = AIOrchestrator(db)
    result = await orchestrator.execute(
        agent_name="resume_agent",
        task="rewrite",
        user_id=str(current_user["_id"]),
        payload={"resume_text": resume.get("raw_text", ""), "job_description": body.job_description},
    )

    # Save new resume version
    new_resume_doc = {
        "user_id": str(current_user["_id"]),
        "filename": f"optimized_{resume.get('filename', 'resume')}",
        "file_path": resume.get("file_path", ""),
        "file_type": resume.get("file_type", "pdf"),
        "file_size": resume.get("file_size", 0),
        "raw_text": resume.get("raw_text", ""),
        "parsed_sections": resume.get("parsed_sections", {}),
        "skills_extracted": result.data.get("rewritten_skills", []),
        "is_active": False,
        "version_number": resume.get("version_number", 1) + 1,
        "label": f"ATS Optimized - {body.target_role or 'General'}",
        "parent_resume_id": resume_id,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    new_id = await repo.insert(new_resume_doc)

    background_tasks.add_task(
        _log_timeline,
        db,
        str(current_user["_id"]),
        "RESUME_REWRITTEN",
        "Resume rewritten and ATS-optimized",
        {"original_id": resume_id, "new_id": new_id},
    )

    return ResumeOptimizeResponse(
        original_resume_id=resume_id,
        new_resume_id=new_id,
        changes_made=result.data.get("changes_made", []),
        improvement_score=result.data.get("improvement_score", 0.0),
        optimized_sections={
            "summary": result.data.get("rewritten_summary", ""),
            "experience": result.data.get("rewritten_experience", []),
            "skills": result.data.get("rewritten_skills", []),
            "keywords_added": result.data.get("keywords_added", []),
        },
    )


@router.get("/{resume_id}/versions")
async def get_resume_versions(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    repo = ResumeRepository(db)
    versions = await repo.get_versions(resume_id, str(current_user["_id"]))
    return {"success": True, "versions": versions}


@router.get("/{resume_id}/download")
async def download_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    import os
    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume or resume.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Resume", resume_id)
    file_path = resume.get("generated_file_path") or resume.get("file_path", "")
    if not file_path or not os.path.exists(file_path):
        raise NotFoundError("Resume file", resume_id)
    return FileResponse(
        path=file_path,
        filename=resume.get("filename", "resume.pdf"),
        media_type="application/octet-stream",
    )


async def _log_timeline(db, user_id: str, event_type: str, title: str, metadata: dict):
    from datetime import datetime
    await db["ai_timeline"].insert_one({
        "user_id": user_id,
        "event_type": event_type,
        "title": title,
        "description": title,
        "metadata": metadata,
        "created_at": datetime.utcnow(),
    })