"""
Resume API Endpoints — Upload, Parse, Analyze, Optimize, Download, Preview
"""
from typing import Optional

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, UploadFile, File, BackgroundTasks
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.dependencies import get_db, get_current_user
from app.core.exceptions import NotFoundError, ResumeParseError, ValidationError
from app.repositories.ats_repo import ATSRepository
from app.repositories.resume_repo import ResumeRepository
from app.repositories.job_repo import JobRepository
from app.services.storage_service import StorageService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_generator_service import ResumeGeneratorService
from app.schemas.resume import ResumeUploadResponse, ResumeListItem, ResumeAnalysisResponse, ResumeOptimizeRequest, ResumeOptimizeResponse
from app.ai.orchestrator import AIOrchestrator

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
    await repo.save_version({
        "resume_id": resume_id,
        "root_resume_id": resume_id,
        "user_id": str(current_user["_id"]),
        "version_number": version_number,
        "label": "Original Upload",
        "filename": file.filename or "resume",
        "file_path": file_meta["file_path"],
        "file_type": file_meta["file_type"],
        "raw_text": parsed.get("raw_text", ""),
        "parsed_sections": parsed.get("sections", {}),
        "skills_extracted": parsed.get("skills_found", []),
        "source": "upload",
        "changes_made": ["Original resume uploaded and parsed."],
        "target_role": None,
        "created_at": datetime.now(timezone.utc),
    })

    # Update user skills
    if parsed.get("skills_found"):
        await db["users"].update_one(
            {"_id": current_user["_id"]},
            {"$addToSet": {"skills": {"$each": parsed["skills_found"]}}}
        )

    # NEW: immediate baseline ATS score so the user sees it right after upload
    generic_jd = _build_generic_job_description(parsed, (current_user.get("preferred_roles") or [None])[0])
    orchestrator = AIOrchestrator(db)
    ats_result = await orchestrator.execute(
        agent_name="ats_agent",
        task="score",
        user_id=str(current_user["_id"]),
        payload={"resume_text": parsed.get("raw_text", ""), "job_description": generic_jd},
    )
    ats_data = ats_result.data if ats_result.success else {}
    ats_report_id = None
    if ats_result.success:
        ats_repo = ATSRepository(db)
        ats_report_id = await ats_repo.insert({
            "user_id": str(current_user["_id"]),
            "resume_id": resume_id,
            "job_description_snippet": generic_jd[:200],
            "ats_score": ats_data.get("ats_score", 0.0),
            "keyword_coverage": ats_data.get("keyword_coverage", {}),
            "missing_keywords": ats_data.get("missing_keywords", []),
            "section_analysis": ats_data.get("section_analysis", {}),
            "formatting_issues": ats_data.get("formatting_issues", []),
            "skill_relevance": ats_data.get("skill_relevance", 0.0),
            "industry_alignment": ats_data.get("industry_alignment", 0.0),
            "improvement_plan": ats_data.get("improvement_plan", []),
            "predicted_pass_rate": ats_data.get("predicted_pass_rate", 0.0),
            "full_report": ats_data,
            "created_at": datetime.now(timezone.utc),
        })
        await db["users"].update_one(
            {"_id": current_user["_id"]},
            {"$set": {"latest_ats_score": ats_data.get("ats_score", 0.0)}}
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
        ats_score=ats_data.get("ats_score", 0.0),
        ats_report_id=ats_report_id,
        missing_keywords=ats_data.get("missing_keywords", []),
        formatting_issues=ats_data.get("formatting_issues", []),
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
    background_tasks: BackgroundTasks,
    target_role: str = "",
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

    job_description = body.job_description or ""
    target_role = body.target_role
    if not job_description.strip():
        job_repo = JobRepository(db)
        jobs = await job_repo.find_by_user(str(current_user["_id"]), limit=1)
        if jobs:
            job = jobs[0]
            job_description = _job_to_description(job)
            target_role = target_role or job.get("title")
    if not job_description.strip():
        job_description = _build_generic_job_description(
            {"skills_found": resume.get("skills_extracted", [])},
            target_role,
        )

    orchestrator = AIOrchestrator(db)
    baseline_ats = await _score_optimized_resume(
        orchestrator,
        str(current_user["_id"]),
        resume.get("raw_text", ""),
        job_description,
    )
    baseline_score = float(baseline_ats.get("ats_score", 0) or 0)

    result = await orchestrator.execute(
        agent_name="resume_agent",
        task="rewrite",
        user_id=str(current_user["_id"]),
        payload={"resume_text": resume.get("raw_text", ""), "job_description": job_description},
    )
    if not result.success:
        raise ValidationError(f"Resume optimization failed: {result.error or 'AI service error'}")

    candidate_data = _build_optimized_resume_data(resume, result.data)
    candidate_text = _resume_data_to_text(candidate_data)
    candidate_ats = await _score_optimized_resume(
        orchestrator,
        str(current_user["_id"]),
        candidate_text,
        job_description,
    )
    ats_target_score = 95
    best_result = result
    best_data = candidate_data
    best_text = candidate_text
    best_ats = candidate_ats
    best_score = float(candidate_ats.get("ats_score", 0) or 0)

    for _ in range(4):
        if best_score >= ats_target_score:
            break
        retry_result = await orchestrator.execute(
            agent_name="resume_agent",
            task="rewrite",
            user_id=str(current_user["_id"]),
            payload={
                "resume_text": _repair_resume_context(resume.get("raw_text", ""), best_text),
                "job_description": _job_description_with_ats_feedback(job_description, best_ats),
            },
        )
        if retry_result.success:
            retry_data = _build_optimized_resume_data(resume, retry_result.data)
            retry_text = _resume_data_to_text(retry_data)
            retry_ats = await _score_optimized_resume(
                orchestrator,
                str(current_user["_id"]),
                retry_text,
                job_description,
            )
            retry_score = float(retry_ats.get("ats_score", 0) or 0)
            # Never let a later repair overwrite a stronger earlier draft.
            if retry_score > best_score:
                best_result = retry_result
                best_data = retry_data
                best_text = retry_text
                best_ats = retry_ats
                best_score = retry_score
        else:
            break

    if best_score <= baseline_score:
        raise ValidationError(
            f"No safe ATS improvement was produced (current {baseline_score:.0f}, best draft {best_score:.0f}). "
            "Your current resume was kept active. Add a specific job description or more truthful achievements and try again."
        )

    result = best_result
    optimized_data = best_data
    optimized_text = best_text
    ats_result = best_ats

    meets_ats_target = best_score >= ats_target_score
    ats_quality_warning = None
    if not meets_ats_target:
        ats_quality_warning = {
            "message": "Resume optimized, but it did not reach the strict ATS target without adding unverified content.",
            "required_score": ats_target_score,
            "projected_ats_score": best_score,
            "remaining_issues": ats_result.get("formatting_issues", []),
            "missing_keywords": ats_result.get("missing_keywords", []),
            "next_step": "Add more truthful achievements, metrics, project details, contact details, and job-specific evidence to the source resume.",
        }

    generator = ResumeGeneratorService()
    generated_file_path = await generator.generate_docx(optimized_data, str(current_user["_id"]))
    generated_file_size = _safe_file_size(generated_file_path)

    # Save new resume version
    new_resume_doc = {
        "user_id": str(current_user["_id"]),
        "filename": _optimized_filename(resume.get("filename", "resume")),
        "file_path": resume.get("file_path", ""),
        "generated_file_path": generated_file_path,
        "generated_file_type": "docx",
        "file_type": "docx",
        "file_size": generated_file_size,
        "latest_ats_score": ats_result.get("ats_score", 0.0),
        "raw_text": optimized_text,
        "parsed_sections": {
            "summary": optimized_data.get("summary", ""),
            "experience": optimized_data.get("experience", []),
            "education": optimized_data.get("education", []),
            "projects": optimized_data.get("projects", []),
            "skills": optimized_data.get("skills", []),
            "certifications": optimized_data.get("certifications", []),
        },
        "skills_extracted": result.data.get("rewritten_skills", []),
        "is_active": False,
        "version_number": resume.get("version_number", 1) + 1,
        "label": f"ATS Optimized - {target_role or 'General'}",
        "parent_resume_id": resume_id,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    new_id = await repo.insert(new_resume_doc)
    # The recreated resume becomes the user's current pipeline resume only
    # after it has been generated and ATS-checked successfully.
    await repo.set_active(str(current_user["_id"]), new_id)

    ats_repo = ATSRepository(db)
    await ats_repo.insert({
        "user_id": str(current_user["_id"]),
        "resume_id": new_id,
        "job_description_snippet": job_description[:200],
        "ats_score": ats_result.get("ats_score", 0.0),
        "keyword_coverage": ats_result.get("keyword_coverage", {}),
        "missing_keywords": ats_result.get("missing_keywords", []),
        "section_analysis": ats_result.get("section_analysis", {}),
        "formatting_issues": ats_result.get("formatting_issues", []),
        "skill_relevance": ats_result.get("skill_relevance", 0.0),
        "industry_alignment": ats_result.get("industry_alignment", 0.0),
        "improvement_plan": ats_result.get("improvement_plan", []),
        "predicted_pass_rate": ats_result.get("predicted_pass_rate", 0.0),
        "full_report": ats_result,
        "created_at": datetime.now(timezone.utc),
    })
    await db["users"].update_one(
        {"_id": current_user["_id"]},
        {"$set": {"latest_ats_score": ats_result.get("ats_score", 0.0)}},
    )
    root_resume_id = resume.get("parent_resume_id") or resume_id
    await repo.save_version({
        "resume_id": new_id,
        "root_resume_id": root_resume_id,
        "parent_resume_id": resume_id,
        "user_id": str(current_user["_id"]),
        "version_number": new_resume_doc["version_number"],
        "label": new_resume_doc["label"],
        "filename": new_resume_doc["filename"],
        "file_path": generated_file_path,
        "file_type": "docx",
        "generated_file_path": generated_file_path,
        "raw_text": optimized_text,
        "parsed_sections": new_resume_doc["parsed_sections"],
        "skills_extracted": new_resume_doc["skills_extracted"],
        "source": "ai_rewrite",
        "changes_made": result.data.get("changes_made", []),
        "target_role": target_role,
        "ats_target_score": ats_target_score,
        "projected_ats_score": ats_result.get("ats_score", 0.0),
        "projected_pass_rate": ats_result.get("predicted_pass_rate", 0.0),
        "missing_keywords_after_optimization": ats_result.get("missing_keywords", []),
        "improvement_score": result.data.get("improvement_score", 0.0),
        "quality_audit": result.data.get("quality_audit", {}),
        "meets_ats_target": meets_ats_target,
        "ats_quality_warning": ats_quality_warning,
        "download_url": f"/api/v1/resume/{new_id}/download",
        "created_at": datetime.now(timezone.utc),
    })

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
            "remaining_risks": result.data.get("remaining_risks", []),
            "ats_target_score": ats_target_score,
            "original_ats_score": baseline_score,
            "projected_ats_score": ats_result.get("ats_score", 0.0),
            "verified_score_improvement": round(best_score - baseline_score, 2),
            "predicted_pass_rate": ats_result.get("predicted_pass_rate", 0.0),
            "missing_keywords_after_optimization": ats_result.get("missing_keywords", []),
            "quality_audit": result.data.get("quality_audit", {}),
            "meets_ats_target": meets_ats_target,
            "ats_quality_warning": ats_quality_warning,
            "download_url": f"/api/v1/resume/{new_id}/download",
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


@router.get("/{resume_id}/preview")
async def preview_resume(
    resume_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Return a PDF of the resume suitable for inline browser preview.

    Strategy (in priority order):
    1. If a generated_file_path exists and ends in .pdf  → serve it directly.
    2. If generated_file_path exists and ends in .docx   → convert to PDF
       using WeasyPrint via ResumeGeneratorService, cache the PDF path.
    3. If only original file_path (the uploaded file) exists:
       - .pdf  → serve directly.
       - .docx → convert to PDF.
    4. If nothing works → 404.

    The PDF is returned with Content-Disposition: inline so the browser
    renders it in-tab instead of triggering a download.
    """
    import os
    import tempfile

    repo = ResumeRepository(db)
    resume = await repo.get_by_id(resume_id)
    if not resume or resume.get("user_id") != str(current_user["_id"]):
        raise NotFoundError("Resume", resume_id)

    # ── 1. Determine the best source file ──────────────────────────────
    generated_path = resume.get("generated_file_path", "") or ""
    original_path = resume.get("file_path", "") or ""

    source_path = ""
    if generated_path and os.path.exists(generated_path):
        source_path = generated_path
    elif original_path and os.path.exists(original_path):
        source_path = original_path

    if not source_path:
        raise NotFoundError("Resume file", resume_id)

    # ── 2. If already a PDF → serve inline ─────────────────────────────
    if source_path.lower().endswith(".pdf"):
        return FileResponse(
            path=source_path,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )

    # ── 3. DOCX → PDF via WeasyPrint ───────────────────────────────────
    # Check if we already converted this resume to PDF and cached it
    cached_pdf_path = resume.get("preview_pdf_path", "") or ""
    if cached_pdf_path and os.path.exists(cached_pdf_path):
        return FileResponse(
            path=cached_pdf_path,
            media_type="application/pdf",
            headers={"Content-Disposition": "inline"},
        )

    # Need to generate PDF from the optimized resume data stored in the doc
    # Build resume_data dict for the template — reuse _build_preview_data
    resume_data = _build_preview_resume_data(resume)

    try:
        generator = ResumeGeneratorService()
        pdf_path = await generator.generate_pdf(
            resume_data=resume_data,
            template="resume_ats_clean",
            user_id=str(current_user["_id"]),
        )
    except Exception as e:
        import structlog
        structlog.get_logger().error("preview_pdf_generation_failed",
                                     resume_id=resume_id, error=str(e))
        raise NotFoundError("Preview PDF (generation failed)", resume_id)

    # Cache the generated PDF path so next preview is instant
    await repo.update(resume_id, {"preview_pdf_path": pdf_path})

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


# ---------------------------------------------------------------------------
# INTERNAL HELPERS
# ---------------------------------------------------------------------------

def _build_preview_resume_data(resume: dict) -> dict:
    """
    Construct the template-compatible dict from what's stored in the
    resume MongoDB document. Used exclusively by the preview endpoint
    to avoid re-running AI when we already have optimized data saved.
    """
    parsed_sections = resume.get("parsed_sections", {}) or {}
    raw_text = resume.get("raw_text", "")

    # Contact — try parsed_sections first, then extract from raw_text
    contact = parsed_sections.get("contact") or _extract_contact_from_text(raw_text)

    # Skills — from extracted list or parsed_sections
    skills = (
        resume.get("skills_extracted")
        or parsed_sections.get("skills")
        or []
    )

    # Summary
    summary = parsed_sections.get("summary", "")
    if isinstance(summary, list):
        summary = " ".join(summary)

    # Experience
    experience = parsed_sections.get("experience", []) or []

    # Education
    education = parsed_sections.get("education", []) or []

    # Projects
    projects = parsed_sections.get("projects", []) or []

    # Full name — try to infer from raw_text
    full_name = resume.get("full_name", "") or _guess_name(raw_text)

    return {
        "full_name": full_name,
        "contact": contact if isinstance(contact, dict) else {},
        "summary": summary if isinstance(summary, str) else "",
        "skills": skills if isinstance(skills, list) else [],
        "experience": experience if isinstance(experience, list) else [],
        "education": education if isinstance(education, list) else [],
        "projects": projects if isinstance(projects, list) else [],
        "certifications": parsed_sections.get("certifications", []) or [],
    }


def _build_optimized_resume_data(original_resume: dict, ai_data: dict) -> dict:
    raw_text = original_resume.get("raw_text", "")
    original_sections = original_resume.get("parsed_sections", {}) or {}
    extracted_contact = _extract_contact_from_text(raw_text)
    ai_contact = ai_data.get("contact", {}) or {}
    # Empty AI fields must not erase valid contact details from the upload.
    contact = {
        key: ai_contact.get(key) or extracted_contact.get(key, "")
        for key in ("email", "phone", "linkedin", "location")
    }
    data = {
        "full_name": ai_data.get("full_name") or _guess_name(raw_text),
        "contact": contact,
        "summary": ai_data.get("rewritten_summary") or original_sections.get("summary", ""),
        "experience": ai_data.get("rewritten_experience") or original_sections.get("experience", []) or [],
        "education": ai_data.get("education") or original_sections.get("education", []) or [],
        "projects": ai_data.get("projects") or original_sections.get("projects", []) or [],
        "skills": ai_data.get("rewritten_skills", []) or original_resume.get("skills_extracted", []),
        "certifications": ai_data.get("certifications") or original_sections.get("certifications", []) or [],
    }
    return _polish_resume_data(data)


def _polish_resume_data(data: dict) -> dict:
    data["summary"] = _clean_sentence(data.get("summary", ""), ensure_period=True)
    data["skills"] = _dedupe_preserve_order([_clean_skill(skill) for skill in data.get("skills", [])])[:28]
    polished_experience = []
    used_starts = {}
    for exp in data.get("experience", []):
        exp = dict(exp)
        bullets = []
        for bullet in exp.get("bullets", []):
            clean = _clean_bullet(str(bullet))
            if not clean:
                continue
            clean = _reduce_repeated_start(clean, used_starts)
            bullets.append(clean)
        exp["bullets"] = _dedupe_preserve_order(bullets)[:6]
        polished_experience.append(exp)
    data["experience"] = polished_experience
    polished_projects = []
    for project in data.get("projects", []):
        project = dict(project)
        project["description"] = _clean_sentence(project.get("description", ""), ensure_period=True)
        project["technologies"] = _dedupe_preserve_order([_clean_skill(t) for t in project.get("technologies", [])])
        polished_projects.append(project)
    data["projects"] = polished_projects
    return data


def _clean_sentence(text: str, ensure_period: bool = False) -> str:
    import re
    text = str(text or "").replace("•", "").replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text).strip(" -\t\r\n")
    replacements = {
        "responsible for": "owned",
        "worked on": "contributed to",
        "helped with": "supported",
        "utilized": "used",
        "various": "multiple",
    }
    for bad, good in replacements.items():
        text = re.sub(rf"\b{re.escape(bad)}\b", good, text, flags=re.IGNORECASE)
    text = re.sub(r"\bi\b", "I", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    if ensure_period and text and text[-1] not in ".!?":
        text += "."
    return text


def _clean_bullet(text: str) -> str:
    import re
    text = _clean_sentence(text, ensure_period=True)
    text = re.sub(r"^(responsible for|worked on|helped|handled|did)\b", "Delivered", text, flags=re.IGNORECASE)
    words = text.split()
    if len(words) > 32:
        text = " ".join(words[:32]).rstrip(",;:")
        if text[-1] not in ".!?":
            text += "."
    return text


def _clean_skill(skill: str) -> str:
    import re
    skill = re.sub(r"\s+", " ", str(skill or "")).strip(" ,;|")
    return skill


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        key = item.lower().strip()
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _reduce_repeated_start(text: str, used_starts: dict) -> str:
    alternatives = {
        "developed": "Built",
        "implemented": "Delivered",
        "created": "Designed",
        "managed": "Led",
        "worked": "Contributed",
        "used": "Applied",
        "improved": "Enhanced",
        "optimized": "Streamlined",
    }
    words = text.split()
    if not words:
        return text
    start = words[0].lower().strip(",.;:")
    used_starts[start] = used_starts.get(start, 0) + 1
    if used_starts[start] > 1 and start in alternatives:
        words[0] = alternatives[start]
        return " ".join(words)
    return text


def _resume_data_to_text(data: dict) -> str:
    lines = [data.get("full_name", "").strip()]
    contact = data.get("contact", {})
    contact_line = " | ".join(str(contact.get(k, "")).strip() for k in ("email", "phone", "linkedin", "location") if contact.get(k))
    if contact_line:
        lines.append(contact_line)
    if data.get("summary"):
        lines.extend(["", "PROFESSIONAL SUMMARY", data["summary"]])
    if data.get("skills"):
        lines.extend(["", "SKILLS", ", ".join(data["skills"])])
    if data.get("experience"):
        lines.extend(["", "WORK EXPERIENCE"])
        for exp in data["experience"]:
            header = " - ".join(filter(None, [exp.get("title", ""), exp.get("company", "")]))
            dates = " - ".join(filter(None, [exp.get("start_date", ""), exp.get("end_date", "")]))
            lines.append(header)
            if dates or exp.get("location"):
                lines.append(" | ".join(filter(None, [dates, exp.get("location", "")])))
            lines.extend(f"- {bullet}" for bullet in exp.get("bullets", []))
    if data.get("projects"):
        lines.extend(["", "PROJECTS"])
        for project in data["projects"]:
            lines.append(project.get("name", "Project"))
            if project.get("description"):
                lines.append(project["description"])
            if project.get("technologies"):
                lines.append("Technologies: " + ", ".join(project["technologies"]))
    if data.get("education"):
        lines.extend(["", "EDUCATION"])
        for edu in data["education"]:
            lines.append(" - ".join(filter(None, [edu.get("degree", ""), edu.get("institution", ""), edu.get("year", "")])))
    if data.get("certifications"):
        lines.extend(["", "CERTIFICATIONS"])
        for certification in data["certifications"]:
            if isinstance(certification, dict):
                lines.append(" - ".join(str(value) for value in certification.values() if value))
            else:
                lines.append(str(certification))
    return "\n".join(line for line in lines if line is not None).strip()


def _repair_resume_context(original_text: str, current_text: str) -> str:
    return (
        "ORIGINAL RESUME FACTS - use these as the truth source and do not invent beyond them:\n"
        f"{original_text[:5000]}\n\n"
        "CURRENT OPTIMIZED DRAFT THAT FAILED STRICT ATS CHECKS - repair this draft:\n"
        f"{current_text[:5000]}"
    )


def _guess_name(text: str) -> str:
    for line in text.splitlines()[:8]:
        clean = line.strip()
        if clean and "@" not in clean and not any(ch.isdigit() for ch in clean) and len(clean.split()) <= 5:
            return clean
    return "Candidate"


def _job_to_description(job: dict) -> str:
    parts = [
        f"Title: {job.get('title', '')}",
        f"Company: {job.get('company', '')}",
        f"Location: {job.get('location', '')}",
        job.get("description", ""),
    ]
    if job.get("requirements"):
        parts.append("Requirements: " + ", ".join(str(item) for item in job["requirements"]))
    if job.get("required_skills"):
        parts.append("Required skills: " + ", ".join(str(item) for item in job["required_skills"]))
    if job.get("nice_to_have_skills"):
        parts.append("Nice to have: " + ", ".join(str(item) for item in job["nice_to_have_skills"]))
    return "\n".join(part for part in parts if part)


def _extract_contact_from_text(text: str) -> dict:
    import re
    email = re.search(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", text)
    phone = re.search(r"(\+?\d[\d().\-\s]{7,}\d)", text)
    linkedin = re.search(r"(?:https?://)?(?:www\.)?linkedin\.com/in/[\w-]+", text, re.IGNORECASE)
    return {
        "email": email.group(0) if email else "",
        "phone": phone.group(0).strip() if phone else "",
        "linkedin": linkedin.group(0) if linkedin else "",
        "location": "",
    }


def _optimized_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0] if "." in filename else filename
    return f"optimized_{stem}.docx"


def _safe_file_size(file_path: str) -> int:
    import os
    try:
        return os.path.getsize(file_path)
    except OSError:
        return 0


def _quality_audit_passed(ai_data: dict) -> bool:
    audit = ai_data.get("quality_audit") or {}
    if not audit:
        return False
    required_flags = (
        "contact_ready",
        "section_ready",
        "impact_ready",
        "grammar_ready",
        "repetition_ready",
        "tailoring_ready",
    )
    flags_ok = all(bool(audit.get(flag)) for flag in required_flags)
    try:
        estimated_score = float(audit.get("estimated_external_checker_score", 0) or 0)
    except (TypeError, ValueError):
        estimated_score = 0.0
    return flags_ok and estimated_score >= 80


def _build_generic_job_description(parsed: dict, target_role_hint: Optional[str]) -> str:
    skills = parsed.get("skills_found", []) or []
    role = target_role_hint or (f"{skills[0]} Professional" if skills else "General Professional Role")
    skills_phrase = ", ".join(skills[:10]) or "the candidate's core domain"
    return (
        f"A {role} role at a competitive technology company. "
        f"Looking for strong skills in {skills_phrase} with relevant hands-on experience. "
        "Evaluate against general industry best practices for this role."
    )

async def _score_optimized_resume(
    orchestrator: AIOrchestrator,
    user_id: str,
    resume_text: str,
    job_description: str,
) -> dict:
    result = await orchestrator.execute(
        agent_name="ats_agent",
        task="score",
        user_id=user_id,
        payload={
            "resume_text": resume_text,
            "job_description": job_description,
        },
        store_result=False,
    )
    return result.data if result.success else {
        "ats_score": 0.0,
        "missing_keywords": [],
        "formatting_issues": [result.error or "ATS scoring failed"],
        "improvement_plan": [],
        "predicted_pass_rate": 0.0,
    }


def _job_description_with_ats_feedback(job_description: str, ats_result: dict) -> str:
    missing_keywords = ", ".join(ats_result.get("missing_keywords", [])[:20]) or "None"
    formatting_issues = ", ".join(ats_result.get("formatting_issues", [])[:10]) or "None"
    improvement_plan = "; ".join(
        str(item.get("action", item)) for item in ats_result.get("improvement_plan", [])[:8]
    ) or "Improve keyword alignment, section clarity, and measurable impact."
    return (
        f"{job_description}\n\n"
        "ATS OPTIMIZATION FEEDBACK FOR REPAIR PASS:\n"
        f"- Current projected ATS score: {ats_result.get('ats_score', 0)}/100\n"
        "- Required internal target: 90+/100 where truthful based on the candidate's original experience.\n"
        "- External checker target: 80+ in content, ATS essentials, HR red flags, discrimination safety, seniority, tailoring, grammar, repetition, and quantified impact.\n"
        "- Required standard sections in generated document: Contact, Professional Summary, Skills, Work Experience, Projects when useful, Education, Certifications when present.\n"
        f"- Missing or weak keywords to naturally include if truthful: {missing_keywords}\n"
        f"- Formatting/section issues to fix: {formatting_issues}\n"
        f"- Priority fixes: {improvement_plan}\n"
        "- Mandatory repair checklist: improve quantified impact, remove repeated words/action verbs, fix spelling and grammar, make bullet punctuation consistent, strengthen ATS essentials, reduce HR red flags, and improve seniority/tailoring language.\n"
        "Rewrite again to close these gaps without inventing employers, titles, dates, degrees, tools, or exact metrics."
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
