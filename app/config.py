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
    # AI - GROQ ONLY (free tier, no credit card required)
    # ==========================================
    # NOTE: mistral-saba-24b was deprecated by Groq on 07/30/2025 and
    # mixtral-8x7b-32768 on 03/20/2025 - both return errors now. Your .env
    # uses llama-3.3-70b-versatile as primary and llama-3.1-8b-instant as
    # fallback, both currently live, stable Groq models - kept as-is here.
    GROQ_API_KEY: str = ""
    GROQ_PRIMARY_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: str = "llama-3.1-8b-instant"
    GROQ_MAX_RETRIES: int = 3

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


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()