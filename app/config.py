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
    # ------------------------------------------
    # Provider chain (in order): GROQ -> MISTRAL -> GEMINI
    # Each provider has up to 5 API keys that are round-robined per
    # request (request 1 -> key 1, request 2 -> key 2, ... request 6 ->
    # key 1 again). This spreads load across keys so per-key free-tier
    # quotas last longer.
    #
    # If a call fails/rate-limits on EVERY key of the current provider,
    # the whole provider is considered exhausted for that call and the
    # client automatically falls through to the next provider in the
    # chain. Only the keys you actually fill in .env are used — empty
    # slots are skipped automatically, so you don't need all 5 for every
    # provider to get started.
    # ==========================================

    # --- Groq (primary). Open-source Llama/Mixtral family models. ---
    GROQ_API_KEY_1: str = ""
    GROQ_API_KEY_2: str = ""
    GROQ_API_KEY_3: str = ""
    GROQ_API_KEY_4: str = ""
    GROQ_API_KEY_5: str = ""
    # NOTE: mistral-saba-24b was deprecated by Groq on 07/30/2025 and
    # mixtral-8x7b-32768 on 03/20/2025 - both return errors now. Using
    # currently-live, stable, open-source Groq models instead.
    GROQ_PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MAX_RETRIES: int = 3

    # --- Mistral (2nd fallback provider). Official api.mistral.ai. ---
    # Open-weight Mistral models (e.g. open-mistral-7b / mistral-small).
    MISTRAL_API_KEY_1: str = ""
    MISTRAL_API_KEY_2: str = ""
    MISTRAL_API_KEY_3: str = ""
    MISTRAL_API_KEY_4: str = ""
    MISTRAL_API_KEY_5: str = ""
    # --- Mistral (2nd fallback provider)
    MISTRAL_PRIMARY_MODEL: str = "mistral-small-latest"   # rolling alias, auto-updates
    MISTRAL_FALLBACK_MODEL: str = "mistral-medium-latest"  # rolling alias, auto-updates
     # confirmed active till Oct 16, 2026
    MISTRAL_MAX_RETRIES: int = 3

    # --- Gemini (3rd / last fallback provider). Free-tier friendly. ---
    GEMINI_API_KEY_1: str = ""
    GEMINI_API_KEY_2: str = ""
    GEMINI_API_KEY_3: str = ""
    GEMINI_API_KEY_4: str = ""
    GEMINI_API_KEY_5: str = ""
   
    GEMINI_PRIMARY_MODEL: str = "gemini-flash-latest"       # official rolling alias
    GEMINI_FALLBACK_MODEL: str = "gemini-2.5-flash-lite"     # confirmed active till Oct 16, 2026
    GEMINI_MAX_RETRIES: int = 3

    # Overall LLM behavior
    LLM_PROVIDER_ORDER: str = "groq,mistral,gemini"  # comma-separated, order = fallback order

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
    # Kept for backward compatibility with code that still reads
    # GENERATED_FILES_PATH (e.g. storage_service.py's save_generated_file).
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
    # Comma-separated in .env; use the cors_origins_list property below
    # to get an actual list[str] wherever main.py needs it.
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

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS as a clean list, e.g. for FastAPI's allow_origins=."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_resume_types_list(self) -> list[str]:
        """ALLOWED_RESUME_TYPES as a clean list, e.g. ['pdf', 'docx']."""
        return [t.strip().lower() for t in self.ALLOWED_RESUME_TYPES.split(",") if t.strip()]

    @property
    def groq_api_keys(self) -> list[str]:
        """All non-empty Groq keys, in order — used for round-robin rotation."""
        keys = [self.GROQ_API_KEY_1, self.GROQ_API_KEY_2, self.GROQ_API_KEY_3,
                self.GROQ_API_KEY_4, self.GROQ_API_KEY_5]
        return [k.strip() for k in keys if k and k.strip()]

    @property
    def mistral_api_keys(self) -> list[str]:
        """All non-empty Mistral keys, in order — used for round-robin rotation."""
        keys = [self.MISTRAL_API_KEY_1, self.MISTRAL_API_KEY_2, self.MISTRAL_API_KEY_3,
                self.MISTRAL_API_KEY_4, self.MISTRAL_API_KEY_5]
        return [k.strip() for k in keys if k and k.strip()]

    @property
    def gemini_api_keys(self) -> list[str]:
        """All non-empty Gemini keys, in order — used for round-robin rotation."""
        keys = [self.GEMINI_API_KEY_1, self.GEMINI_API_KEY_2, self.GEMINI_API_KEY_3,
                self.GEMINI_API_KEY_4, self.GEMINI_API_KEY_5]
        return [k.strip() for k in keys if k and k.strip()]

    @property
    def llm_provider_order_list(self) -> list[str]:
        """Provider fallback order as a list, e.g. ['groq', 'mistral', 'gemini']."""
        return [p.strip().lower() for p in self.LLM_PROVIDER_ORDER.split(",") if p.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()