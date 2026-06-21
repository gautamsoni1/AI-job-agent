"""
Application Configuration — pydantic-settings based
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ==========================================
    # APPLICATION
    # ==========================================
    APP_NAME: str = "AI Job Agent"
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = "http://localhost:3000"
    ALGORITHM: str = "HS256"

    # ==========================================
    # MONGODB
    # ==========================================
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "ai_job_agent"

    # ==========================================
    # JWT
    # ==========================================
    JWT_SECRET_KEY: str = "your-super-secret-key-min-32-chars-here!!"
    JWT_REFRESH_SECRET: str = "your-refresh-secret-key-min-32-chars!!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ==========================================
    # AI — MULTI-PROVIDER, MULTI-KEY, OPEN-SOURCE MODELS ONLY
    # ==========================================

    # --- Groq (primary). Open-source Llama/Mixtral family models. ---
    GROQ_API_KEY_1: str = ""
    GROQ_API_KEY_2: str = ""
    GROQ_API_KEY_3: str = ""
    GROQ_API_KEY_4: str = ""
    GROQ_API_KEY_5: str = ""
    GROQ_PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MAX_RETRIES: int = 3

    # --- Mistral (2nd fallback provider). Official api.mistral.ai. ---
    MISTRAL_API_KEY_1: str = ""
    MISTRAL_API_KEY_2: str = ""
    MISTRAL_API_KEY_3: str = ""
    MISTRAL_API_KEY_4: str = ""
    MISTRAL_API_KEY_5: str = ""
    MISTRAL_PRIMARY_MODEL: str = "mistral-small-latest"
    MISTRAL_FALLBACK_MODEL: str = "mistral-medium-latest"
    MISTRAL_MAX_RETRIES: int = 3

    # --- Gemini (3rd / last fallback provider). Free-tier friendly. ---
    GEMINI_API_KEY_1: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""
    GEMINI_API_KEY_4: str = ""
    GEMINI_API_KEY_5: str = ""
    GEMINI_PRIMARY_MODEL: str = "gemini-flash-latest"
    GEMINI_FALLBACK_MODEL: str = "gemini-2.5-flash-lite"
    GEMINI_MAX_RETRIES: int = 3

    # Overall LLM behavior
    LLM_PROVIDER_ORDER: str = "groq,mistral,gemini"

    # ==========================================
    # CHROMADB (OPEN SOURCE)
    # ==========================================
    CHROMA_DB_PATH: str = "./chroma_db"

    # ==========================================
    # EMBEDDINGS (OPEN SOURCE)
    # ==========================================
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # ==========================================
    # FILE STORAGE
    # ==========================================
    UPLOAD_PATH: str = "./uploads"
    GENERATED_RESUME_PATH: str = "./generated_resumes"
    GENERATED_COVER_LETTER_PATH: str = "./generated_cover_letters"
    GENERATED_FILES_PATH: str = "./generated_files"

    # ==========================================
    # APIFY (FREE TRIAL)
    # ==========================================
    APIFY_TOKEN: str = ""
    APIFY_LINKEDIN_ACTOR: str = "curious_coder/linkedin-jobs-scraper"
    APIFY_INDEED_ACTOR: str = "borderline/indeed-scraper"
    APIFY_NAUKRI_ACTOR: str = "muhammetakkurtt/naukri-job-scraper"
    APIFY_GLASSDOOR_ACTOR: str = "valig/glassdoor-jobs-scraper"

    # ==========================================
    # GOOGLE SHEETS (FREE)
    # ==========================================
    GOOGLE_SHEET_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "service_account.json"

    # ==========================================
    # EMAIL (FREE)
    # ==========================================
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_USERNAME: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_FROM_NAME: str = "AI Job Agent"

    # ==========================================
    # RESUME SETTINGS
    # ==========================================
    MAX_RESUME_SIZE_MB: int = 10
    ALLOWED_RESUME_TYPES: str = "pdf,docx"

    # ==========================================
    # ATS SETTINGS
    # ==========================================
    ATS_PASSING_SCORE: int = 70
    ATS_HIGH_SCORE: int = 85

    # ==========================================
    # JOB MATCHING
    # ==========================================
    TOP_MATCH_LIMIT: int = 20
    MIN_MATCH_SCORE: int = 60

    # ==========================================
    # AI MEMORY
    # ==========================================
    MEMORY_MAX_HISTORY: int = 100
    MEMORY_CONTEXT_LIMIT: int = 20

    # ==========================================
    # CACHE
    # ==========================================
    CACHE_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 3600

    # ==========================================
    # RATE LIMITING
    # ==========================================
    RATE_LIMIT_PER_MINUTE: int = 100

    # ==========================================
    # CORS
    # ==========================================
    CORS_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    # ==========================================
    # STRUCTLOG
    # ==========================================
    LOG_JSON_FORMAT: bool = True

    # ==========================================
    # DEVELOPMENT
    # ==========================================
    DEBUG: bool = True
    AUTO_RELOAD: bool = True

    # ------------------------------------------------------------------
    # COMPUTED PROPERTIES
    # ------------------------------------------------------------------

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_resume_types_list(self) -> list[str]:
        return [t.strip().lower() for t in self.ALLOWED_RESUME_TYPES.split(",") if t.strip()]

    @property
    def groq_api_keys(self) -> list[str]:
        keys = [self.GROQ_API_KEY_1, self.GROQ_API_KEY_2, self.GROQ_API_KEY_3,
                self.GROQ_API_KEY_4, self.GROQ_API_KEY_5]
        return [k.strip() for k in keys if k and k.strip()]

    @property
    def mistral_api_keys(self) -> list[str]:
        keys = [self.MISTRAL_API_KEY_1, self.MISTRAL_API_KEY_2, self.MISTRAL_API_KEY_3,
                self.MISTRAL_API_KEY_4, self.MISTRAL_API_KEY_5]
        return [k.strip() for k in keys if k and k.strip()]

    @property
    def gemini_api_keys(self) -> list[str]:
        keys = [self.GEMINI_API_KEY_1, self.GEMINI_API_KEY_2, self.GEMINI_API_KEY_3,
                self.GEMINI_API_KEY_4, self.GEMINI_API_KEY_5]
        return [k.strip() for k in keys if k and k.strip()]

    @property
    def llm_provider_order_list(self) -> list[str]:
        return [p.strip().lower() for p in self.LLM_PROVIDER_ORDER.split(",") if p.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


# ==========================================
# STARTUP VALIDATOR
# Called once from app/main.py lifespan, before the server accepts
# any requests. Raises RuntimeError with a clear message so the
# developer sees exactly what is missing in .env instead of getting
# a cryptic crash on the first real request.
# ==========================================

_PLACEHOLDER_PREFIXES = (
    "your-",           # JWT defaults
    "apify_api_token", # Apify placeholder
)


def _is_placeholder_or_empty(value: str) -> bool:
    """Return True if the value is empty or one of the known placeholders."""
    v = (value or "").strip()
    if not v:
        return True
    for prefix in _PLACEHOLDER_PREFIXES:
        if v.lower().startswith(prefix):
            return True
    return False


def validate_startup_config() -> None:
    """
    Validate critical environment variables at server startup.

    Rules
    -----
    HARD FAILURES (server refuses to start):
      - JWT_SECRET_KEY / JWT_REFRESH_SECRET still set to the insecure defaults.
      - Not a single valid LLM API key across all three providers
        (Groq + Mistral + Gemini). At least one provider must be ready
        or every AI feature will fail immediately.

    WARNINGS (server starts, but logs a clear message):
      - APIFY_TOKEN is missing / placeholder → job discovery disabled.
      - EMAIL_USERNAME is empty → email features disabled.
      - GOOGLE_SHEET_ID is empty → Google Sheets sync disabled.
      - MongoDB URI still on localhost in a non-development environment.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # --- JWT secrets ---
    if _is_placeholder_or_empty(settings.JWT_SECRET_KEY):
        errors.append(
            "JWT_SECRET_KEY is not set or still uses the insecure default. "
            "Set a random 32+ character secret in .env."
        )
    if _is_placeholder_or_empty(settings.JWT_REFRESH_SECRET):
        errors.append(
            "JWT_REFRESH_SECRET is not set or still uses the insecure default. "
            "Set a random 32+ character secret in .env."
        )

    # --- At least one LLM provider must have a valid key ---
    has_groq = bool(settings.groq_api_keys)
    has_mistral = bool(settings.mistral_api_keys)
    has_gemini = bool(settings.gemini_api_keys)

    if not has_groq and not has_mistral and not has_gemini:
        errors.append(
            "No LLM API keys found. Set at least one of: "
            "GROQ_API_KEY_1, MISTRAL_API_KEY_1, or GEMINI_API_KEY_1 in .env. "
            "All AI features (resume analysis, ATS scoring, job matching, etc.) will fail without this."
        )
    else:
        # Individual provider warnings so the developer knows what fallbacks are available
        if not has_groq:
            warnings.append("GROQ_API_KEY_1..5 are all empty — Groq provider disabled (Mistral/Gemini will be used as fallback).")
        if not has_mistral:
            warnings.append("MISTRAL_API_KEY_1..5 are all empty — Mistral provider disabled.")
        if not has_gemini:
            warnings.append("GEMINI_API_KEY_1..5 are all empty — Gemini fallback provider disabled.")

    # --- Apify (optional but needed for job discovery) ---
    apify = (settings.APIFY_TOKEN or "").strip()
    if not apify or apify.lower() in ("apify_api_token", ""):
        warnings.append(
            "APIFY_TOKEN is not set or still uses the placeholder value. "
            "Job discovery (LinkedIn / Indeed / Naukri / Glassdoor) will be disabled."
        )

    # --- Email (optional) ---
    if not (settings.EMAIL_USERNAME or "").strip():
        warnings.append(
            "EMAIL_USERNAME is empty — email features (verification, password reset, application emails) are disabled."
        )

    # --- Google Sheets (optional) ---
    if not (settings.GOOGLE_SHEET_ID or "").strip():
        warnings.append(
            "GOOGLE_SHEET_ID is empty — Google Sheets job sync is disabled."
        )

    # --- MongoDB URI sanity check in production ---
    if settings.APP_ENV not in ("development", "dev", "local"):
        if "localhost" in settings.MONGODB_URI or "127.0.0.1" in settings.MONGODB_URI:
            warnings.append(
                f"MONGODB_URI points to localhost but APP_ENV is '{settings.APP_ENV}'. "
                "Make sure this is intentional — use MongoDB Atlas URI in production."
            )

    # --- Emit results ---
    import structlog
    log = structlog.get_logger("startup_validator")

    for warning in warnings:
        log.warning("config_warning", message=warning)

    if errors:
        error_block = "\n".join(f"  ❌  {e}" for e in errors)
        raise RuntimeError(
            f"\n\n{'='*70}\n"
            f"STARTUP ABORTED — Fix the following .env issues and restart:\n\n"
            f"{error_block}\n\n"
            f"{'='*70}\n"
        )

    log.info(
        "config_ok",
        llm_providers=[
            p for p, ok in [("groq", has_groq), ("mistral", has_mistral), ("gemini", has_gemini)] if ok
        ],
        apify_ready=bool(apify and apify.lower() != "apify_api_token"),
        email_ready=bool((settings.EMAIL_USERNAME or "").strip()),
        sheets_ready=bool((settings.GOOGLE_SHEET_ID or "").strip()),
    )