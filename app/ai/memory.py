from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = structlog.get_logger()


@dataclass
class SkillSnapshot:
    skills: list[str]
    recorded_at: datetime
    source: str  # "resume_parse", "job_match", "ats_analysis"


@dataclass
class ATSSnapshot:
    score: float
    job_title: str
    recorded_at: datetime
    report_id: str


@dataclass
class PreferenceSignal:
    signal_type: str  # "job_saved", "job_skipped", "applied", "cover_letter_generated"
    entity_id: str
    entity_data: dict
    recorded_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class UserMemory:
    user_id: str
    full_name: str
    email: str
    skills: list[str] = field(default_factory=list)
    experience_years: int = 0
    preferred_roles: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    career_goals: str = ""
    latest_resume_text: str = ""
    resume_version_count: int = 0
    ats_trend: list[ATSSnapshot] = field(default_factory=list)
    latest_ats_score: float = 0.0
    jobs_viewed_count: int = 0
    jobs_saved_count: int = 0
    jobs_applied_count: int = 0
    application_success_rate: float = 0.0
    interview_rate: float = 0.0
    agent_history: list[dict] = field(default_factory=list)
    skill_snapshots: list[SkillSnapshot] = field(default_factory=list)
    preference_signals: list[PreferenceSignal] = field(default_factory=list)

    def to_prompt_context(self) -> str:
        """Serialize memory into a prompt-ready string."""
        ats_str = ""
        if self.ats_trend:
            scores = [f"{s.score:.0f} ({s.job_title})" for s in self.ats_trend[-5:]]
            ats_str = f"ATS Score History (last 5): {', '.join(scores)}"

        recent_history = ""
        if self.agent_history:
            recent = self.agent_history[-3:]
            recent_history = "; ".join([
                f"{h.get('agent')} {h.get('task')} on {h.get('created_at', '')[:10]}"
                for h in recent
            ])

        return f"""
USER PROFILE:
- Name: {self.full_name}
- Experience: {self.experience_years} years
- Skills: {', '.join(self.skills[:30])}
- Preferred Roles: {', '.join(self.preferred_roles)}
- Preferred Locations: {', '.join(self.preferred_locations)}
- Career Goals: {self.career_goals}

JOB SEARCH ACTIVITY:
- Jobs Viewed: {self.jobs_viewed_count}
- Jobs Saved: {self.jobs_saved_count}
- Applications Submitted: {self.jobs_applied_count}
- Application Response Rate: {self.application_success_rate:.1f}%
- Interview Conversion Rate: {self.interview_rate:.1f}%

ATS PERFORMANCE:
- Latest ATS Score: {self.latest_ats_score:.0f}/100
- {ats_str}

RECENT AI ACTIONS:
{recent_history if recent_history else "None yet"}
""".strip()


class AIMemoryManager:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def load_user_memory(self, user_id: str) -> UserMemory:
        """Load comprehensive user memory from MongoDB."""
        user = await self.db["users"].find_one({"_id": __import__("bson").ObjectId(user_id)})
        if not user:
            return UserMemory(user_id=user_id, full_name="Unknown", email="")

        # Load latest resume
        resume = await self.db["resumes"].find_one(
            {"user_id": user_id, "is_active": True},
            sort=[("created_at", -1)]
        )
        latest_resume_text = ""
        if resume:
            latest_resume_text = resume.get("parsed_data", {}).get("raw_text", "")[:3000]

        # Load ATS trend
        ats_docs = await self.db["ats_reports"].find(
            {"user_id": user_id},
            sort=[("created_at", 1)]
        ).limit(10).to_list(length=10)
        ats_trend = [
            ATSSnapshot(
                score=doc.get("ats_score", 0),
                job_title=doc.get("job_title", ""),
                recorded_at=doc.get("created_at", datetime.utcnow()),
                report_id=str(doc.get("_id", ""))
            )
            for doc in ats_docs
        ]

        # Load application stats
        total_apps = await self.db["applications"].count_documents({"user_id": user_id})
        responded = await self.db["applications"].count_documents({
            "user_id": user_id,
            "status": {"$in": ["IN_REVIEW", "INTERVIEW_SCHEDULED", "OFFERED"]}
        })
        interviews = await self.db["applications"].count_documents({
            "user_id": user_id,
            "status": "INTERVIEW_SCHEDULED"
        })

        success_rate = round((responded / total_apps * 100), 2) if total_apps > 0 else 0.0
        interview_rate = round((interviews / total_apps * 100), 2) if total_apps > 0 else 0.0

        # Load recent agent history
        timeline_docs = await self.db["ai_timeline"].find(
            {"user_id": user_id},
            sort=[("created_at", -1)]
        ).limit(10).to_list(length=10)

        jobs_saved = await self.db["jobs"].count_documents({"user_id": user_id, "is_saved": True})
        jobs_viewed = await self.db["jobs"].count_documents({"user_id": user_id})

        return UserMemory(
            user_id=user_id,
            full_name=f"{user.get('first_name', '')} {user.get('last_name', '')}".strip(),
            email=user.get("email", ""),
            skills=user.get("skills", []),
            experience_years=user.get("experience_years", 0),
            preferred_roles=user.get("preferred_roles", []),
            preferred_locations=user.get("preferred_locations", []),
            career_goals=user.get("career_goals", ""),
            latest_resume_text=latest_resume_text,
            resume_version_count=await self.db["resumes"].count_documents({"user_id": user_id}),
            ats_trend=ats_trend,
            latest_ats_score=ats_trend[-1].score if ats_trend else 0.0,
            jobs_viewed_count=jobs_viewed,
            jobs_saved_count=jobs_saved,
            jobs_applied_count=total_apps,
            application_success_rate=success_rate,
            interview_rate=interview_rate,
            agent_history=[
                {"agent": d.get("event_type", ""), "task": d.get("title", ""), "created_at": str(d.get("created_at", ""))}
                for d in timeline_docs
            ],
        )

    async def save_agent_result(self, user_id: str, agent: str, task: str, result: dict) -> bool:
        """Store agent result in MongoDB for memory."""
        try:
            doc = {
                "user_id": user_id,
                "agent": agent,
                "task": task,
                "result_summary": {k: v for k, v in result.items() if k != "raw_text"},
                "created_at": datetime.utcnow(),
            }
            await self.db["agent_results"].insert_one(doc)
            return True
        except Exception as e:
            logger.error("save_agent_result_failed", error=str(e))
            return False

    async def get_skill_progression(self, user_id: str) -> list[SkillSnapshot]:
        """Track how user's skills have grown over time."""
        docs = await self.db["ats_reports"].find(
            {"user_id": user_id},
            {"keyword_coverage": 1, "created_at": 1},
            sort=[("created_at", 1)]
        ).limit(20).to_list(length=20)

        snapshots = []
        for doc in docs:
            coverage = doc.get("keyword_coverage", {})
            skills_present = [k for k, v in coverage.items() if v]
            snapshots.append(SkillSnapshot(
                skills=skills_present,
                recorded_at=doc.get("created_at", datetime.utcnow()),
                source="ats_analysis"
            ))
        return snapshots

    async def get_ats_trend(self, user_id: str) -> list[ATSSnapshot]:
        """Return ATS score history for trend analysis."""
        docs = await self.db["ats_reports"].find(
            {"user_id": user_id},
            sort=[("created_at", 1)]
        ).limit(20).to_list(length=20)
        return [
            ATSSnapshot(
                score=doc.get("ats_score", 0),
                job_title=doc.get("job_title", ""),
                recorded_at=doc.get("created_at", datetime.utcnow()),
                report_id=str(doc.get("_id", ""))
            )
            for doc in docs
        ]

    async def update_preferences(self, user_id: str, signal: PreferenceSignal) -> bool:
        """Store a user preference signal."""
        try:
            await self.db["preference_signals"].insert_one({
                "user_id": user_id,
                "signal_type": signal.signal_type,
                "entity_id": signal.entity_id,
                "entity_data": signal.entity_data,
                "recorded_at": signal.recorded_at,
            })
            return True
        except Exception as e:
            logger.error("update_preferences_failed", error=str(e))
            return False