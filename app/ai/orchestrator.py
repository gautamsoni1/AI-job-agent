"""
Central AI Orchestrator — Single entry point for ALL AI agent calls.
Never call agents directly. Always go through here.
"""
import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import structlog
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.ai.groq_client import GroqClient
from app.ai.memory import AIMemoryManager, UserMemory

logger = structlog.get_logger()


@dataclass
class AgentResult:
    success: bool
    data: dict
    agent_name: str
    task: str
    error: Optional[str] = None
    raw_response: Optional[str] = None


class AIOrchestrator:
    """
    Central coordinator for all AI operations.

    Responsibilities:
    - Agent lifecycle management
    - User memory loading and injection
    - Retry logic (3 attempts with exponential backoff)
    - Result storage in MongoDB
    - AI Timeline event logging
    - Structured error recovery
    """

    MAX_RETRIES = 3

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.groq_client = GroqClient()
        self.memory_manager = AIMemoryManager(db)

    async def execute(
        self,
        agent_name: str,
        task: str,
        user_id: str,
        payload: dict,
        store_result: bool = True,
    ) -> AgentResult:
        """
        Main orchestration method:
        1. Load user memory from MongoDB
        2. Initialize the correct agent
        3. Inject memory into payload
        4. Execute with retry logic
        5. Store result
        6. Log to AI Timeline
        7. Return structured result
        """
        log = logger.bind(agent=agent_name, task=task, user_id=user_id)

        # 1. Load user memory
        try:
            memory = await self.memory_manager.load_user_memory(user_id)
        except Exception as e:
            log.warning("memory_load_failed", error=str(e))
            memory = None

        # 2. Get agent instance
        agent = self._get_agent(agent_name)
        if agent is None:
            return AgentResult(
                success=False,
                data={},
                agent_name=agent_name,
                task=task,
                error=f"Unknown agent: {agent_name}",
            )

        # 3. Execute with retry
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                result_data = await self._dispatch(agent, task, memory, payload)
                log.info("agent_success", attempt=attempt + 1)

                # 4. Store result
                if store_result and memory:
                    await self.memory_manager.save_agent_result(user_id, agent_name, task, result_data)

                # 5. Log timeline event
                await self._log_timeline(user_id, agent_name, task, result_data)

                return AgentResult(
                    success=True,
                    data=result_data,
                    agent_name=agent_name,
                    task=task,
                )

            except Exception as e:
                last_error = e
                wait_time = 2 ** attempt
                log.warning("agent_attempt_failed", attempt=attempt + 1, error=str(e), retry_in=wait_time)
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(wait_time)

        log.error("agent_all_retries_failed", error=str(last_error))
        return AgentResult(
            success=False,
            data={},
            agent_name=agent_name,
            task=task,
            error=str(last_error),
        )

    def _get_agent(self, agent_name: str):
        """Instantiate the correct agent by name."""
        from app.ai.agents.resume_agent import ResumeAgent
        from app.ai.agents.ats_agent import ATSAgent
        from app.ai.agents.job_scout_agent import JobScoutAgent
        from app.ai.agents.job_matching_agent import JobMatchingAgent
        from app.ai.agents.cover_letter_agent import CoverLetterAgent
        from app.ai.agents.application_agent import ApplicationAgent
        from app.ai.agents.career_coach_agent import CareerCoachAgent
        from app.ai.agents.interview_agent import InterviewAgent
        from app.ai.agents.market_intel_agent import MarketIntelAgent
        from app.ai.agents.user_insight_agent import UserInsightAgent

        registry = {
            "resume_agent": ResumeAgent,
            "ats_agent": ATSAgent,
            "job_scout_agent": JobScoutAgent,
            "job_matching_agent": JobMatchingAgent,
            "cover_letter_agent": CoverLetterAgent,
            "application_agent": ApplicationAgent,
            "career_coach_agent": CareerCoachAgent,
            "interview_agent": InterviewAgent,
            "market_intel_agent": MarketIntelAgent,
            "user_insight_agent": UserInsightAgent,
        }

        cls = registry.get(agent_name)
        if cls is None:
            return None
        return cls(self.groq_client, self.memory_manager)

    async def _dispatch(self, agent, task: str, memory: Optional[UserMemory], payload: dict) -> dict:
        """Route the task to the correct agent method and return data dict."""
        # Inject memory into all payload calls
        if memory is not None:
            payload = {"memory": memory, **payload}

        method = getattr(agent, task, None)
        if method is None or not callable(method):
            raise ValueError(f"Agent {agent.agent_name!r} has no task {task!r}")

        result = await method(**payload)

        if isinstance(result, dict):
            return result
        # Handle dataclass or object results
        if hasattr(result, "__dict__"):
            return result.__dict__
        return {"result": result}

    async def _log_timeline(self, user_id: str, agent_name: str, task: str, data: dict):
        """Log the AI action to the timeline collection."""
        event_map = {
            ("resume_agent", "analyze"): "RESUME_ANALYZED",
            ("resume_agent", "rewrite"): "RESUME_REWRITTEN",
            ("ats_agent", "score"): "ATS_SCORED",
            ("ats_agent", "improvement_plan"): "ATS_IMPROVED",
            ("job_scout_agent", "scout"): "JOB_SCOUTED",
            ("job_matching_agent", "match"): "JOB_MATCHED",
            ("cover_letter_agent", "generate"): "COVER_LETTER_GENERATED",
            ("application_agent", "assess_readiness"): "APPLICATION_PREPARED",
            ("career_coach_agent", "generate_roadmap"): "CAREER_ROADMAP_GENERATED",
            ("career_coach_agent", "analyze_gap"): "CAREER_ROADMAP_GENERATED",
            ("career_coach_agent", "weekly_goals"): "SKILL_RECOMMENDED",
            ("interview_agent", "generate_questions"): "INTERVIEW_PREP_GENERATED",
            ("interview_agent", "evaluate_answer"): "INTERVIEW_ANSWER_EVALUATED",
            ("market_intel_agent", "analyze_market"): "MARKET_ANALYSIS_RUN",
            ("user_insight_agent", "generate_insights"): "CAREER_HEALTH_CALCULATED",
        }

        event_type = event_map.get((agent_name, task), "CAREER_HEALTH_CALCULATED")
        title_map = {
            "resume_agent": f"Resume {task.replace('_', ' ').title()}",
            "ats_agent": f"ATS {task.replace('_', ' ').title()}",
            "job_scout_agent": "Job Scouted",
            "job_matching_agent": "Job Matched",
            "cover_letter_agent": "Cover Letter Generated",
            "application_agent": "Application Readiness Assessed",
            "career_coach_agent": f"Career Coach: {task.replace('_', ' ').title()}",
            "interview_agent": f"Interview: {task.replace('_', ' ').title()}",
            "market_intel_agent": "Market Analysis Completed",
            "user_insight_agent": "User Insights Generated",
        }

        try:
            await self.db["ai_timeline"].insert_one({
                "user_id": user_id,
                "event_type": event_type,
                "agent_name": agent_name,
                "task": task,
                "title": title_map.get(agent_name, f"{agent_name}: {task}"),
                "description": f"AI agent {agent_name} completed task {task}",
                "metadata": {k: v for k, v in data.items() if k not in ("raw_text", "content") and isinstance(v, (str, int, float, bool, list))},
                "created_at": datetime.now(timezone.utc),
            })
        except Exception as e:
            logger.warning("timeline_log_failed", error=str(e))