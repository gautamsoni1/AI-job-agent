"""
Pipeline Service — single orchestrator: resume parse → AI analyze → ATS
score/auto-improve → domain-accurate, experience-matched, de-duplicated job
discovery/scouting/matching → sheet export → honest apply.
"""
from datetime import datetime, timezone
from typing import Optional

import structlog
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.ai.orchestrator import AIOrchestrator
from app.repositories.resume_repo import ResumeRepository
from app.repositories.job_repo import JobRepository
from app.repositories.application_repo import ApplicationRepository
from app.repositories.ats_repo import ATSRepository
from app.repositories.pipeline_repo import PipelineRunRepository
from app.services.storage_service import StorageService
from app.services.resume_parser_service import ResumeParserService
from app.services.resume_generator_service import ResumeGeneratorService
from app.services.sheet_export_service import SheetExportService
from app.services.apify_service import ApifyService
from app.services.google_sheets_service import GoogleSheetsService
from app.services.email_service import EmailService
from app.utils.text_cleaner import extract_email
from app.utils.experience_utils import (
    infer_experience_years,
    experience_level_for,
    job_requires_more_experience,
)

from app.api.v1.resume import (
    _build_optimized_resume_data,
    _resume_data_to_text,
    _job_description_with_ats_feedback,
    _repair_resume_context,
    _optimized_filename,
    _safe_file_size,
)
from app.api.v1.jobs import _to_job_response

logger = structlog.get_logger()
settings = get_settings()

ATS_TARGET_SCORE = 80
MAX_ATS_ITERATIONS = 2
MIN_OVERALL_MATCH = 40  # AI match score below this = not relevant enough, dropped


class PipelineService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.resume_repo = ResumeRepository(db)
        self.job_repo = JobRepository(db)
        self.app_repo = ApplicationRepository(db)
        self.ats_repo = ATSRepository(db)
        self.pipeline_repo = PipelineRunRepository(db)
        self.orchestrator = AIOrchestrator(db)

    # ------------------------------------------------------------------
    # MAIN ENTRY POINT
    # ------------------------------------------------------------------
    async def run_pipeline(
        self,
        user: dict,
        file_bytes: bytes,
        filename: str,
        target_role: Optional[str],
        job_description: Optional[str],
        locations: Optional[list[str]],
        max_jobs: int,
    ) -> dict:
        user_id = str(user["_id"])
        now = datetime.now(timezone.utc)

        # 1. Save + parse resume
        storage = StorageService()
        file_meta = await storage.save_resume(file_bytes, filename, user_id)
        parser = ResumeParserService()
        parsed = await parser.parse(file_meta["file_path"], file_meta["file_type"])

        existing = await self.resume_repo.find_by_user(user_id)
        version_number = len(existing) + 1
        resume_doc = {
            "user_id": user_id,
            "filename": filename,
            "file_path": file_meta["file_path"],
            "file_type": file_meta["file_type"],
            "file_size": file_meta["size_bytes"],
            "raw_text": parsed.get("raw_text", ""),
            "parsed_sections": parsed.get("sections", {}),
            "skills_extracted": parsed.get("skills_found", []),
            "is_active": True,
            "version_number": version_number,
            "created_at": now,
            "updated_at": now,
        }
        await self.db["resumes"].update_many({"user_id": user_id}, {"$set": {"is_active": False}})
        resume_id = await self.resume_repo.insert(resume_doc)
        resume_doc["_id"] = resume_id

        if parsed.get("skills_found"):
            await self.db["users"].update_one(
                {"_id": user["_id"]},
                {"$addToSet": {"skills": {"$each": parsed["skills_found"]}}},
            )
        await self._log_timeline(user_id, "RESUME_UPLOADED", f"Resume uploaded: {filename}", {"resume_id": resume_id})

        # 2. AI analysis
        await self.orchestrator.execute(
            agent_name="resume_agent", task="analyze", user_id=user_id,
            payload={"resume_text": resume_doc["raw_text"], "target_role": target_role or ""},
        )

        # 3. Job description for ATS scoring
        inferred_role = self._infer_role_from_resume(parsed)
        effective_jd = (job_description or "").strip()
        if not effective_jd:
            role_for_jd = target_role or inferred_role
            top_skills = ", ".join(parsed.get("skills_found", [])[:10])
            skills_phrase = top_skills if top_skills else "the candidate's core domain"
            effective_jd = (
                f"A {role_for_jd} role at a competitive technology company. "
                f"Looking for strong skills in {skills_phrase} "
                "with relevant hands-on experience. Evaluate against general industry best practices for this role."
            )

        # 4. ATS score + auto-improve loop
        current_text = resume_doc["raw_text"]
        latest_resume_doc = resume_doc
        latest_resume_id = resume_id
        iteration = 0

        ats_result = await self.orchestrator.execute(
            agent_name="ats_agent", task="score", user_id=user_id,
            payload={"resume_text": current_text, "job_description": effective_jd},
        )
        ats_data = ats_result.data
        initial_ats_score = ats_data.get("ats_score", 0.0)

        while ats_data.get("ats_score", 0) < ATS_TARGET_SCORE and iteration < MAX_ATS_ITERATIONS:
            iteration += 1
            jd_for_rewrite = effective_jd if iteration == 1 else _job_description_with_ats_feedback(effective_jd, ats_data)
            text_for_rewrite = current_text if iteration == 1 else _repair_resume_context(resume_doc["raw_text"], current_text)

            rewrite_result = await self.orchestrator.execute(
                agent_name="resume_agent", task="rewrite", user_id=user_id,
                payload={"resume_text": text_for_rewrite, "job_description": jd_for_rewrite},
            )
            if not rewrite_result.success:
                break

            optimized_data = _build_optimized_resume_data(latest_resume_doc, rewrite_result.data)
            optimized_text = _resume_data_to_text(optimized_data)
            generator = ResumeGeneratorService()
            generated_path = await generator.generate_docx(optimized_data, user_id)

            new_doc = {
                "user_id": user_id,
                "filename": _optimized_filename(latest_resume_doc.get("filename", "resume")),
                "file_path": latest_resume_doc.get("file_path", ""),
                "generated_file_path": generated_path,
                "generated_file_type": "docx",
                "file_type": "docx",
                "file_size": _safe_file_size(generated_path),
                "raw_text": optimized_text,
                "parsed_sections": {
                    "summary": optimized_data.get("summary", ""),
                    "experience": optimized_data.get("experience", []),
                    "education": optimized_data.get("education", []),
                    "projects": optimized_data.get("projects", []),
                    "skills": optimized_data.get("skills", []),
                },
                "skills_extracted": rewrite_result.data.get("rewritten_skills", []),
                "is_active": False,
                "version_number": latest_resume_doc.get("version_number", version_number) + 1,
                "label": f"Pipeline Auto-Optimized (iter {iteration})",
                "parent_resume_id": resume_id,
                "created_at": now,
                "updated_at": now,
            }
            new_id = await self.resume_repo.insert(new_doc)
            await self.resume_repo.save_version({
                "resume_id": new_id, "root_resume_id": resume_id, "parent_resume_id": resume_id,
                "user_id": user_id, "version_number": new_doc["version_number"], "label": new_doc["label"],
                "filename": new_doc["filename"], "file_path": generated_path, "file_type": "docx",
                "generated_file_path": generated_path, "raw_text": optimized_text,
                "parsed_sections": new_doc["parsed_sections"], "skills_extracted": new_doc["skills_extracted"],
                "source": "pipeline_auto_rewrite", "changes_made": rewrite_result.data.get("changes_made", []),
                "target_role": target_role, "created_at": now,
            })
            new_doc["_id"] = new_id
            current_text = optimized_text
            latest_resume_doc = new_doc
            latest_resume_id = new_id

            ats_result = await self.orchestrator.execute(
                agent_name="ats_agent", task="score", user_id=user_id,
                payload={"resume_text": current_text, "job_description": effective_jd},
            )
            ats_data = ats_result.data

        if iteration > 0:
            await self.resume_repo.set_active(user_id, latest_resume_id)

        await self._save_ats_report(user_id, latest_resume_id, effective_jd, ats_data)

        # 5. Domain-accurate, deduplicated, experience-matched job discovery
        candidate_years = infer_experience_years(resume_doc["raw_text"])
        candidate_level = experience_level_for(candidate_years)

        keywords = self._build_keywords(target_role, inferred_role, parsed)
        location_list = locations or self._get_user_locations(user)
        apify = ApifyService()
        raw_jobs = await apify.fetch_jobs(keywords, location_list, candidate_level, max_results=max_jobs * 3)

        resume_skill_set = {s.lower() for s in parsed.get("skills_found", [])}
        role_keyword_set = {k.lower() for k in keywords if len(k) > 2}

        seen_keys = set()
        saved_jobs = []

        for raw_job in raw_jobs:
            if len(saved_jobs) >= max_jobs:
                break

            key = self._job_key(raw_job)
            if key in seen_keys:
                continue

            if not self._looks_relevant(raw_job, resume_skill_set, role_keyword_set):
                continue

            exp_text = f"{raw_job.get('experience_required','')} {raw_job.get('description','')[:1000]}"
            if job_requires_more_experience(exp_text, candidate_years):
                continue

            seen_keys.add(key)
            raw_job.update({
                "user_id": user_id, "created_at": now, "discovered_at": now,
                "updated_at": now, "is_saved": False, "is_deleted": False,
            })
            raw_job.setdefault("required_skills", [])

            existing_job = await self.job_repo.find_existing_similar(
                user_id, raw_job.get("title", ""), raw_job.get("company", ""), raw_job.get("apply_link", "")
            )
            if existing_job:
                job_with_id = existing_job
            else:
                ids = await self.job_repo.bulk_insert_jobs([raw_job])
                if not ids:
                    continue
                job_with_id = dict(raw_job)
                job_with_id["_id"] = ids[0]

            job_id_str = str(job_with_id["_id"])

            scout_result = await self.orchestrator.execute(
                agent_name="job_scout_agent", task="scout", user_id=user_id, payload={"job": job_with_id},
            )
            await self.job_repo.update_scout_report(job_id_str, scout_result.data)

            match_result = await self.orchestrator.execute(
                agent_name="job_matching_agent", task="match", user_id=user_id,
                payload={"resume_text": current_text, "job": job_with_id},
            )
            overall_match = match_result.data.get("overall_match", 0)
            if overall_match < MIN_OVERALL_MATCH:
                continue

            await self.job_repo.update_match_score(job_id_str, overall_match, match_result.data)
            job_with_id.update({
                "scout_report": scout_result.data,
                "match_score": overall_match,
                "match_report": match_result.data,
            })
            saved_jobs.append(job_with_id)

            try:
                if settings.GOOGLE_SHEET_ID:
                    sheets = GoogleSheetsService()
                    await sheets.sync_job(job_with_id, match_score=overall_match, ats_score=ats_data.get("ats_score", 0))
            except Exception as e:
                logger.warning("pipeline_sheets_sync_failed", error=str(e))

        saved_jobs.sort(key=lambda j: j.get("match_score", 0), reverse=True)

        # 6. Persist pipeline run + export "before apply" sheet
        pipeline_doc = {
            "user_id": user_id,
            "resume_id": resume_id,
            "final_resume_id": latest_resume_id,
            "final_resume_text": current_text[:6000],
            "target_role": target_role or inferred_role,
            "candidate_experience_level": candidate_level,
            "candidate_experience_years": candidate_years,
            "job_description_used": effective_jd[:2000],
            "initial_ats_score": initial_ats_score,
            "final_ats_score": ats_data.get("ats_score", 0.0),
            "ats_iterations": iteration,
            "job_ids": [str(j["_id"]) for j in saved_jobs],
            "status": "JOBS_READY",
            "before_apply_sheet_path": None,
            "after_apply_sheet_path": None,
            "created_at": now,
            "updated_at": now,
        }
        pipeline_id = await self.pipeline_repo.insert(pipeline_doc)
        pipeline_doc["_id"] = pipeline_id

        exporter = SheetExportService()
        sheet_path = exporter.export_jobs_before_apply(pipeline_id, saved_jobs)
        await self.pipeline_repo.update(pipeline_id, {"before_apply_sheet_path": sheet_path})

        await self._log_timeline(
            user_id, "JOB_DISCOVERED", f"Pipeline found {len(saved_jobs)} matching jobs",
            {"pipeline_id": pipeline_id, "count": len(saved_jobs)},
        )

        if saved_jobs:
            jobs_message = f"Found {len(saved_jobs)} jobs matching your {candidate_level}-level profile and skills."
        else:
            jobs_message = (
                f"No closely matching {candidate_level}-level jobs found right now for these keywords/location — "
                "try a different target role or location."
            )

        return {
            "pipeline_id": pipeline_id,
            "resume_id": resume_id,
            "target_role": target_role or inferred_role,
            "initial_ats_score": initial_ats_score,
            "final_ats_score": ats_data.get("ats_score", 0.0),
            "ats_iterations": iteration,
            "resume_optimized": iteration > 0,
            "optimized_resume_id": latest_resume_id if iteration > 0 else None,
            "jobs_found": len(saved_jobs),
            "jobs": [self._to_pipeline_job_item(j) for j in saved_jobs],
            "before_apply_sheet_url": f"/api/v1/pipeline/{pipeline_id}/download/before-apply",
            "message": (
                f"Resume analyzed{' and ATS-optimized over ' + str(iteration) + ' iteration(s)' if iteration else ''}. "
                + jobs_message
            ),
        }

    # ------------------------------------------------------------------
    # APPLY FLOWS — honest: real email send when possible, manual link otherwise
    # ------------------------------------------------------------------
    async def apply_to_all_jobs(self, user_id: str, pipeline_id: str) -> dict:
        pipeline = await self._get_owned_pipeline(user_id, pipeline_id)
        user = await self.db["users"].find_one({"_id": ObjectId(user_id)})
        now = datetime.now(timezone.utc)
        applied_count = manual_count = failed_count = 0

        for job_id in pipeline.get("job_ids", []):
            job = await self.job_repo.get_by_id(job_id)
            if not job:
                failed_count += 1
                continue
            existing = await self.app_repo.find_by_user_and_job(user_id, job_id)
            if existing:
                status = existing.get("status", "APPLIED")
                if status == "APPLIED":
                    applied_count += 1
                elif status == "MANUAL_APPLY_REQUIRED":
                    manual_count += 1
                else:
                    failed_count += 1
                continue
            try:
                outcome = await self._attempt_real_apply(user, pipeline, job)
                await self.app_repo.insert({
                    "user_id": user_id, "job_id": job_id,
                    "resume_id": pipeline.get("final_resume_id") or pipeline.get("resume_id"),
                    "status": outcome["status"],
                    "applied_at": now if outcome["status"] == "APPLIED" else None,
                    "notes": outcome.get("cover_letter", "")[:2000],
                    "status_history": [{"status": outcome["status"], "changed_at": now, "notes": outcome.get("reason", "")}],
                    "created_at": now, "updated_at": now,
                })
                if outcome["status"] == "APPLIED":
                    applied_count += 1
                elif outcome["status"] == "MANUAL_APPLY_REQUIRED":
                    manual_count += 1
                else:
                    failed_count += 1
                await self._log_timeline(
                    user_id, "APPLICATION_SUBMITTED" if outcome["status"] == "APPLIED" else "APPLICATION_STATUS_CHANGED",
                    f"{outcome['status']} — {job.get('title')} at {job.get('company')}",
                    {"job_id": job_id, "pipeline_id": pipeline_id, "status": outcome["status"]},
                )
            except Exception as e:
                logger.warning("pipeline_apply_failed", job_id=job_id, error=str(e))
                failed_count += 1

        results = await self._build_application_results(pipeline)
        exporter = SheetExportService()
        sheet_path = exporter.export_application_results(pipeline_id, results)
        await self.pipeline_repo.update(pipeline_id, {"after_apply_sheet_path": sheet_path, "status": "APPLIED"})

        return {
            "total": len(pipeline.get("job_ids", [])),
            "applied_count": applied_count,
            "manual_count": manual_count,
            "failed_count": failed_count,
            "results": results,
            "sheet_path": sheet_path,
        }

    async def apply_to_job(self, user_id: str, pipeline_id: str, job_id: str) -> dict:
        pipeline = await self._get_owned_pipeline(user_id, pipeline_id)
        if job_id not in pipeline.get("job_ids", []):
            raise NotFoundError("Job in this pipeline run", job_id)

        job = await self.job_repo.get_by_id(job_id)
        if not job:
            raise NotFoundError("Job", job_id)

        existing = await self.app_repo.find_by_user_and_job(user_id, job_id)
        now = datetime.now(timezone.utc)
        if existing:
            outcome_status = existing.get("status", "APPLIED")
        else:
            user = await self.db["users"].find_one({"_id": ObjectId(user_id)})
            outcome = await self._attempt_real_apply(user, pipeline, job)
            outcome_status = outcome["status"]
            await self.app_repo.insert({
                "user_id": user_id, "job_id": job_id,
                "resume_id": pipeline.get("final_resume_id") or pipeline.get("resume_id"),
                "status": outcome_status,
                "applied_at": now if outcome_status == "APPLIED" else None,
                "notes": outcome.get("cover_letter", "")[:2000],
                "status_history": [{"status": outcome_status, "changed_at": now, "notes": outcome.get("reason", "")}],
                "created_at": now, "updated_at": now,
            })
            await self._log_timeline(
                user_id, "APPLICATION_SUBMITTED" if outcome_status == "APPLIED" else "APPLICATION_STATUS_CHANGED",
                f"{outcome_status} — {job.get('title')} at {job.get('company')}",
                {"job_id": job_id, "pipeline_id": pipeline_id, "status": outcome_status},
            )

        results = await self._build_application_results(pipeline)
        exporter = SheetExportService()
        sheet_path = exporter.export_application_results(pipeline_id, results)
        await self.pipeline_repo.update(pipeline_id, {"after_apply_sheet_path": sheet_path, "status": "APPLIED"})

        return {"already_applied": bool(existing), "status": outcome_status, "sheet_path": sheet_path}

    async def _attempt_real_apply(self, user: dict, pipeline: dict, job: dict) -> dict:
        user_id = str(user["_id"])
        resume_text_for_letter = pipeline.get("final_resume_text", "")

        cl_result = await self.orchestrator.execute(
            agent_name="cover_letter_agent", task="generate", user_id=user_id,
            payload={
                "resume_text": resume_text_for_letter,
                "job": job,
                "company_name": job.get("company", ""),
                "tone": "professional",
            },
        )
        cover_letter_text = cl_result.data.get("full_text", "") if cl_result.success else ""

        contact_email = extract_email(job.get("description", "") or "")
        if contact_email:
            resume_bytes, resume_filename = await self._get_resume_file(
                pipeline.get("final_resume_id") or pipeline.get("resume_id")
            )
            if resume_bytes:
                email_service = EmailService()
                sent = await email_service.send_application_email(
                    to_email=contact_email,
                    candidate_name=f"{user.get('first_name','')} {user.get('last_name','')}".strip(),
                    role=job.get("title", ""),
                    company=job.get("company", ""),
                    cover_letter_text=cover_letter_text,
                    resume_bytes=resume_bytes,
                    resume_filename=resume_filename,
                )
                if sent:
                    return {"status": "APPLIED", "reason": f"Resume emailed to {contact_email}", "cover_letter": cover_letter_text}
                return {"status": "FAILED", "reason": "Email send failed", "cover_letter": cover_letter_text}

        return {
            "status": "MANUAL_APPLY_REQUIRED",
            "reason": "No recruiter email on this posting — only a portal link. Click to finish in one step.",
            "cover_letter": cover_letter_text,
            "apply_link": job.get("apply_link", ""),
        }

    async def _get_resume_file(self, resume_id: str) -> tuple[bytes, str]:
        resume = await self.resume_repo.get_by_id(resume_id)
        if not resume:
            return b"", "resume.pdf"
        path = resume.get("generated_file_path") or resume.get("file_path", "")
        if not path:
            return b"", "resume.pdf"
        storage = StorageService()
        try:
            content = await storage.read_file(path)
        except FileNotFoundError:
            return b"", "resume.pdf"
        ext = "docx" if path.endswith(".docx") else "pdf"
        return content, f"resume.{ext}"

    async def get_sheet_path(self, user_id: str, pipeline_id: str, which: str) -> Optional[str]:
        pipeline = await self._get_owned_pipeline(user_id, pipeline_id)
        key = "before_apply_sheet_path" if which == "before" else "after_apply_sheet_path"
        return pipeline.get(key)

    async def list_runs(self, user_id: str) -> list[dict]:
        runs = await self.pipeline_repo.find_by_user(user_id)
        for r in runs:
            r["_id"] = str(r["_id"])
        return runs

    async def get_pipeline_detail(self, user_id: str, pipeline_id: str) -> dict:
        pipeline = await self._get_owned_pipeline(user_id, pipeline_id)
        jobs = []
        for job_id in pipeline.get("job_ids", []):
            job = await self.job_repo.get_by_id(job_id)
            if job:
                jobs.append(_to_job_response(job))
        pipeline["_id"] = str(pipeline.get("_id", pipeline_id))
        pipeline["jobs"] = jobs
        pipeline["application_status"] = await self._build_application_results(pipeline)
        return pipeline

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------
    async def _get_owned_pipeline(self, user_id: str, pipeline_id: str) -> dict:
        pipeline = await self.pipeline_repo.get_by_id(pipeline_id)
        if not pipeline or pipeline.get("user_id") != user_id:
            raise NotFoundError("Pipeline run", pipeline_id)
        return pipeline

    async def _build_application_results(self, pipeline: dict) -> list[dict]:
        results = []
        for job_id in pipeline.get("job_ids", []):
            job = await self.job_repo.get_by_id(job_id)
            existing = await self.app_repo.find_by_user_and_job(pipeline["user_id"], job_id)
            if not job:
                results.append({"job_id": job_id, "company": "", "title": "", "status": "FAILED", "reason": "Job not found", "applied_at": "", "apply_link": ""})
            elif existing:
                history = existing.get("status_history") or [{}]
                results.append({
                    "job_id": job_id, "company": job.get("company", ""), "title": job.get("title", ""),
                    "status": existing.get("status", "APPLIED"),
                    "reason": history[-1].get("notes", ""),
                    "applied_at": str(existing.get("applied_at", "") or ""),
                    "apply_link": job.get("apply_link", ""),
                })
            else:
                results.append({
                    "job_id": job_id, "company": job.get("company", ""), "title": job.get("title", ""),
                    "status": "NOT_APPLIED", "reason": "Not applied yet", "applied_at": "", "apply_link": job.get("apply_link", ""),
                })
        return results

    def _infer_role_from_resume(self, parsed: dict) -> str:
        skills = parsed.get("skills_found", []) or []
        if skills:
            return f"{skills[0]} Professional"
        return "General Professional Role"

    def _build_keywords(self, target_role: Optional[str], inferred_role: str, parsed: dict) -> list[str]:
        base = target_role.split() if target_role else inferred_role.replace("Professional", "").split()
        skills = parsed.get("skills_found", []) or []
        keywords = list(dict.fromkeys([*base, *skills[:5]]))
        return keywords[:8] or ["Software Engineer"]

    def _get_user_locations(self, user: dict) -> list[str]:
        locs = user.get("preferred_locations") or []
        return locs[:3] if locs else ["India"]

    def _job_key(self, job: dict) -> tuple:
        return (
            (job.get("title") or "").strip().lower(),
            (job.get("company") or "").strip().lower(),
            (job.get("location") or "").strip().lower(),
        )

    def _looks_relevant(self, job: dict, resume_skills: set, role_keywords: set) -> bool:
        if not resume_skills and not role_keywords:
            return True
        text = f"{job.get('title','')} {job.get('description','')[:500]}".lower()
        if any(skill in text for skill in resume_skills):
            return True
        if any(kw in text for kw in role_keywords):
            return True
        return False

    def _to_pipeline_job_item(self, job: dict) -> dict:
        scout = job.get("scout_report", {}) or {}
        return {
            "job_id": str(job.get("_id", "")),
            "title": job.get("title") or "Role not provided",
            "company": job.get("company") or "Company not provided",
            "location": job.get("location"),
            "apply_link": job.get("apply_link"),
            "match_score": job.get("match_score"),
            "relevance_score": scout.get("relevance_score"),
            "salary_range": job.get("salary_range"),
            "required_skills": job.get("required_skills", []) or [],
            "source": job.get("source"),
            "scout_report": scout,
            "match_report": job.get("match_report", {}) or {},
        }

    async def _save_ats_report(self, user_id: str, resume_id: str, jd: str, ats_data: dict):
        report_doc = {
            "user_id": user_id, "resume_id": resume_id, "job_description_snippet": jd[:200],
            "ats_score": ats_data.get("ats_score", 0.0),
            "keyword_coverage": ats_data.get("keyword_coverage", {}),
            "missing_keywords": ats_data.get("missing_keywords", []),
            "section_analysis": ats_data.get("section_analysis", {}),
            "formatting_issues": ats_data.get("formatting_issues", []),
            "skill_relevance": ats_data.get("skill_relevance", 0.0),
            "industry_alignment": ats_data.get("industry_alignment", 0.0),
            "improvement_plan": ats_data.get("improvement_plan", []),
            "predicted_pass_rate": ats_data.get("predicted_pass_rate", 0.0),
            "full_report": ats_data, "created_at": datetime.now(timezone.utc),
        }
        await self.ats_repo.insert(report_doc)
        await self.db["users"].update_one(
            {"_id": ObjectId(user_id)}, {"$set": {"latest_ats_score": ats_data.get("ats_score", 0.0)}}
        )

    async def _log_timeline(self, user_id: str, event_type: str, title: str, metadata: dict):
        await self.db["ai_timeline"].insert_one({
            "user_id": user_id, "event_type": event_type, "title": title, "description": title,
            "metadata": metadata, "created_at": datetime.now(timezone.utc),
        })