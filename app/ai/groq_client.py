import asyncio
import json
from typing import Optional

import structlog
from groq import AsyncGroq

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class GroqClient:
    """
    Centralized Groq API client with retry logic, fallback model,
    and JSON extraction helpers.
    """

    def __init__(self):
        self.client = AsyncGroq(api_key=settings.GROQ_API_KEY)
        self.primary_model = settings.GROQ_PRIMARY_MODEL
        self.fallback_model = settings.GROQ_FALLBACK_MODEL
        self.max_retries = settings.GROQ_MAX_RETRIES

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """Call Groq with retry + fallback logic. Returns raw text content."""
        models_to_try = [self.primary_model, self.fallback_model]
        last_error = None

        for model in models_to_try:
            for attempt in range(self.max_retries):
                try:
                    kwargs = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    if json_mode:
                        kwargs["response_format"] = {"type": "json_object"}

                    response = await self.client.chat.completions.create(**kwargs)
                    content = response.choices[0].message.content
                    logger.info(
                        "groq_call_success",
                        model=model,
                        attempt=attempt + 1,
                        tokens_used=response.usage.total_tokens if response.usage else 0,
                    )
                    return content

                except Exception as e:
                    last_error = e
                    wait_time = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        "groq_call_failed",
                        model=model,
                        attempt=attempt + 1,
                        error=str(e),
                        retry_in=wait_time,
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait_time)

        logger.error("groq_all_attempts_failed", error=str(last_error))
        raise RuntimeError(f"Groq API failed after all retries: {last_error}")

    async def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> dict:
        """Complete and parse JSON response. Returns dict."""
        raw = await self.complete(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=True,
        )
        return self._parse_json(raw)

    def _parse_json(self, text: str) -> dict:
        """Robustly parse JSON from LLM response."""
        text = text.strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip markdown code blocks
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Find JSON object by bracket matching
        start = text.find("{")
        if start != -1:
            depth = 0
            for i, ch in enumerate(text[start:], start):
                if ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i+1])
                        except json.JSONDecodeError:
                            break

        logger.error("groq_json_parse_failed", raw_text=text[:200])
        return {}