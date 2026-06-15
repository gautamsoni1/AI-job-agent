"""
Abstract Base Agent — all AI agents inherit from this.
GROQ + MISTRAL ONLY. Every agent loads prompts from app/prompts/, never inline.
"""
from abc import ABC
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import structlog

from app.ai.groq_client import GroqClient
from app.ai.memory import AIMemoryManager, UserMemory

logger = structlog.get_logger()

PROMPTS_ROOT = Path(__file__).resolve().parent.parent.parent / "prompts"


@dataclass
class AgentContext:
    """Generic context bag passed into agent execution."""
    user_id: str
    task: str
    memory: Optional[UserMemory] = None
    payload: dict = field(default_factory=dict)


@dataclass
class AgentOutput:
    """Generic structured output returned by agents."""
    success: bool
    data: dict
    raw_response: Optional[str] = None
    error: Optional[str] = None


class BaseAgent(ABC):
    """
    Base class for all AI agents.

    - self.client: GroqClient wrapper (Groq API only)
    - self.memory: AIMemoryManager for loading/saving user memory
    - self.model: Mistral model name (informational; GroqClient manages
      primary/fallback selection internally)
    """

    agent_name: str = "base_agent"

    def __init__(self, groq_client: GroqClient, memory: AIMemoryManager):
        self.client = groq_client
        self.memory = memory
        self.model = groq_client.primary_model  # mistral-saba-24b

    async def execute(self, context: AgentContext) -> AgentOutput:
        """
        Default execute() dispatches to a method named after context.task.
        Subclasses with a fixed single responsibility may override this directly.
        """
        method = getattr(self, context.task, None)
        if method is None or not callable(method):
            return AgentOutput(
                success=False,
                data={},
                error=f"Agent '{self.agent_name}' has no task '{context.task}'",
            )
        try:
            result = await method(**context.payload)
            return AgentOutput(success=True, data=result if isinstance(result, dict) else {"result": result})
        except Exception as e:
            logger.error("agent_execute_failed", agent=self.agent_name, task=context.task, error=str(e))
            return AgentOutput(success=False, data={}, error=str(e))

    async def _call_groq(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Call Groq with retry + fallback logic (handled inside GroqClient). Returns raw text."""
        return await self.client.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=False,
        )

    async def _call_groq_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """Call Groq and parse the response as JSON. Returns dict."""
        return await self.client.complete_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    def _load_prompt(self, agent_name: str, task: str) -> str:
        """Load a prompt template from app/prompts/{agent_name}/{task}.txt"""
        path = PROMPTS_ROOT / agent_name / f"{task}.txt"
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8")

    def _render_prompt(self, template: str, **kwargs) -> str:
        """Render a prompt template with simple {placeholder} substitution.

        Curly braces that are part of JSON examples in the template are
        escaped by doubling ({{ }}) in the template files where needed;
        here we only substitute the known placeholders explicitly to avoid
        breaking JSON literals in the templates.
        """
        rendered = template
        for key, value in kwargs.items():
            rendered = rendered.replace(f"{{{key}}}", str(value))
        return rendered