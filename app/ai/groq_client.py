"""
Multi-Provider LLM Client — GROQ -> MISTRAL -> GEMINI fallback chain,
each provider with up to 5 round-robined API keys.

WHY THIS FILE IS STILL CALLED `groq_client.py` / class `GroqClient`:
Every agent (via base_agent.py), the orchestrator, the decision engine,
and a couple of API endpoints (career_coach.py, dashboard.py) import and
instantiate `GroqClient` directly and call `.complete()` / `.complete_json()`
/ read `.primary_model`. To avoid touching every one of those files, this
class keeps the exact same name and public interface, but internally it
is now a full multi-provider, multi-key client.

HOW IT WORKS
------------
1. Each provider (groq, mistral, gemini) gets its own `_KeyRotator`,
   built from up to 5 keys read from Settings. Empty/missing keys are
   skipped automatically — you only need to fill in however many you
   actually have.
2. Round-robin WITHIN a provider: every call to `_KeyRotator.next_key()`
   advances to the next key in that provider's list. So request 1 uses
   key 1, request 2 uses key 2, ... request 6 wraps back to key 1. This
   spreads usage evenly across keys so free-tier quotas last longer.
3. Fallback ACROSS providers: `complete()` tries the current provider
   (Groq by default). Within that provider it will try every one of its
   keys (each with its primary model, then fallback model) before giving
   up on that provider entirely. Only if EVERY key on a provider fails
   does the client move to the next provider in the chain
   (GROQ -> MISTRAL -> GEMINI, configurable via LLM_PROVIDER_ORDER).
4. All models used are open-source / open-weight model families:
   - Groq: Llama 3.x (llama-3.3-70b-versatile / llama-3.1-8b-instant)
   - Mistral: open-mistral-7b / mistral-small-latest (Mistral's official
     API, open-weight model family)
   - Gemini: gemini-1.5-flash (used purely as a last-resort fallback;
     kept here only because it was explicitly requested as the final
     safety net after Groq and Mistral keys are both exhausted)
"""
import asyncio
import json
import itertools
from typing import Optional

import structlog

from app.config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class _KeyRotator:
    """Round-robins through a fixed list of API keys for one provider."""

    def __init__(self, provider: str, keys: list[str]):
        self.provider = provider
        self.keys = keys
        self._cycle = itertools.cycle(keys) if keys else None
        self._lock = asyncio.Lock()

    @property
    def available(self) -> bool:
        return bool(self.keys)

    async def next_key(self) -> Optional[str]:
        """Return the next key in round-robin order, or None if no keys configured."""
        if not self._cycle:
            return None
        async with self._lock:
            return next(self._cycle)


class GroqClient:
    """
    Multi-provider LLM client with round-robin key rotation and automatic
    provider-level fallback. Public interface intentionally mirrors the
    original single-provider GroqClient so no caller needs to change.
    """

    def __init__(self):
        self.max_retries = settings.GROQ_MAX_RETRIES

        # --- Per-provider key rotators ---
        self._rotators = {
            "groq": _KeyRotator("groq", settings.groq_api_keys),
            "mistral": _KeyRotator("mistral", settings.mistral_api_keys),
            "gemini": _KeyRotator("gemini", settings.gemini_api_keys),
        }

        # --- Per-provider model pairs (primary, fallback) ---
        self._models = {
            "groq": (settings.GROQ_PRIMARY_MODEL, settings.GROQ_FALLBACK_MODEL),
            "mistral": (settings.MISTRAL_PRIMARY_MODEL, settings.MISTRAL_FALLBACK_MODEL),
            "gemini": (settings.GEMINI_PRIMARY_MODEL, settings.GEMINI_FALLBACK_MODEL),
        }

        # --- Provider fallback chain, e.g. ["groq", "mistral", "gemini"] ---
        configured_order = settings.llm_provider_order_list or ["groq", "mistral", "gemini"]
        # Only keep providers that actually have at least one key configured.
        self.provider_chain = [p for p in configured_order if self._rotators.get(p) and self._rotators[p].available]

        if not self.provider_chain:
            logger.error("no_llm_providers_configured")

        # Kept for backward compatibility: callers (e.g. base_agent.py)
        # read `groq_client.primary_model` as an informational label.
        # Reflects the primary model of whichever provider is first
        # in the active chain.
        first_provider = self.provider_chain[0] if self.provider_chain else "groq"
        self.primary_model = self._models.get(first_provider, (settings.GROQ_PRIMARY_MODEL, ""))[0]
        self.fallback_model = self._models.get(first_provider, ("", settings.GROQ_FALLBACK_MODEL))[1]

    # ------------------------------------------------------------------
    # PUBLIC API — unchanged signatures
    # ------------------------------------------------------------------
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        json_mode: bool = False,
    ) -> str:
        """
        Try every provider in the fallback chain, in order. Within each
        provider, try every configured key (each with primary then
        fallback model) before moving to the next provider. Returns raw
        text content on first success; raises RuntimeError if every
        provider/key/model combination fails.
        """
        last_error: Optional[Exception] = None

        for provider in self.provider_chain:
            try:
                return await self._complete_with_provider(
                    provider, system_prompt, user_prompt, temperature, max_tokens, json_mode
                )
            except Exception as e:
                last_error = e
                logger.warning(
                    "llm_provider_exhausted",
                    provider=provider,
                    error=str(e),
                    next_provider=self._next_provider_after(provider),
                )
                continue

        logger.error("llm_all_providers_failed", error=str(last_error))
        raise RuntimeError(f"All LLM providers failed: {last_error}")

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

    # ------------------------------------------------------------------
    # INTERNAL — per-provider execution
    # ------------------------------------------------------------------
    async def _complete_with_provider(
        self,
        provider: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        rotator = self._rotators[provider]
        if not rotator.available:
            raise RuntimeError(f"No API keys configured for provider '{provider}'")

        primary_model, fallback_model = self._models[provider]
        models_to_try = [m for m in (primary_model, fallback_model) if m]

        last_error: Optional[Exception] = None
        # Try each key this provider has, round-robin order. For each
        # key, try primary model then fallback model, with retry/backoff.
        num_keys = len(rotator.keys)
        for _ in range(num_keys):
            api_key = await rotator.next_key()
            for model in models_to_try:
                for attempt in range(self.max_retries):
                    try:
                        return await self._call_provider(
                            provider, api_key, model, system_prompt, user_prompt,
                            temperature, max_tokens, json_mode,
                        )
                    except Exception as e:
                        last_error = e
                        wait_time = 2 ** attempt
                        logger.warning(
                            "llm_call_failed",
                            provider=provider,
                            model=model,
                            attempt=attempt + 1,
                            error=str(e),
                            retry_in=wait_time,
                        )
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(wait_time)

        # Every key (and every model) for this provider failed.
        raise RuntimeError(f"Provider '{provider}' failed on all {num_keys} key(s): {last_error}")

    async def _call_provider(
        self,
        provider: str,
        api_key: str,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        json_mode: bool,
    ) -> str:
        if provider == "groq":
            return await self._call_groq(api_key, model, system_prompt, user_prompt, temperature, max_tokens, json_mode)
        if provider == "mistral":
            return await self._call_mistral(api_key, model, system_prompt, user_prompt, temperature, max_tokens, json_mode)
        if provider == "gemini":
            return await self._call_gemini(api_key, model, system_prompt, user_prompt, temperature, max_tokens, json_mode)
        raise ValueError(f"Unknown provider: {provider}")

    # ------------------------------------------------------------------
    # PROVIDER-SPECIFIC CALLS
    # ------------------------------------------------------------------
    async def _call_groq(
        self, api_key: str, model: str, system_prompt: str, user_prompt: str,
        temperature: float, max_tokens: int, json_mode: bool,
    ) -> str:
        from groq import AsyncGroq

        client = AsyncGroq(api_key=api_key)
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

        response = await client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        logger.info(
            "llm_call_success",
            provider="groq",
            model=model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
        )
        return content

    async def _call_mistral(
        self, api_key: str, model: str, system_prompt: str, user_prompt: str,
        temperature: float, max_tokens: int, json_mode: bool,
    ) -> str:
        from mistralai import Mistral

        client = Mistral(api_key=api_key)
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

        response = await client.chat.complete_async(**kwargs)
        content = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        logger.info(
            "llm_call_success",
            provider="mistral",
            model=model,
            tokens_used=getattr(usage, "total_tokens", 0) if usage else 0,
        )
        return content

    async def _call_gemini(
        self, api_key: str, model: str, system_prompt: str, user_prompt: str,
        temperature: float, max_tokens: int, json_mode: bool,
    ) -> str:
        import google.generativeai as genai

        def _sync_call() -> str:
            genai.configure(api_key=api_key)
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            if json_mode:
                generation_config["response_mime_type"] = "application/json"

            gemini_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_prompt,
                generation_config=generation_config,
            )
            result = gemini_model.generate_content(user_prompt)
            return result.text

        # google-generativeai's client is sync-only; run it off the event loop.
        content = await asyncio.to_thread(_sync_call)
        logger.info("llm_call_success", provider="gemini", model=model)
        return content

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------
    def _next_provider_after(self, provider: str) -> Optional[str]:
        try:
            idx = self.provider_chain.index(provider)
        except ValueError:
            return None
        if idx + 1 < len(self.provider_chain):
            return self.provider_chain[idx + 1]
        return None

    def _parse_json(self, text: str) -> dict:
        """Robustly parse JSON from LLM response."""
        text = (text or "").strip()

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
                            return json.loads(text[start:i + 1])
                        except json.JSONDecodeError:
                            break

        logger.error("llm_json_parse_failed", raw_text=text[:200])
        return {}