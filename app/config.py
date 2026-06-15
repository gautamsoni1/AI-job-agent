"""
Application Configuration — pydantic-settings based
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "ai_job_agent"

    # JWT
    JWT_SECRET_KEY: str = "your-super-secret-key-min-32-chars-here!!"
    JWT_REFRESH_SECRET: str = "your-refresh-secret-key-min-32-chars!!"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # AI — GROQ + MISTRAL ONLY
    GROQ_API_KEY: str = ""
    GROQ_PRIMARY_MODEL: str = "mistral-saba-24b"
    GROQ_FALLBACK_MODEL: str = "mixtral-8x7b-32768"
    GROQ_MAX_RETRIES: int = 3

    # Apify
    APIFY_TOKEN: str = ""
    APIFY_LINKEDIN_ACTOR: str = "apify/linkedin-jobs-scraper"
    APIFY_INDEED_ACTOR: str = "misceres/indeed-scraper"

    # Google Sheets
    GOOGLE_SHEET_ID: str = ""
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "service_account.json"

    # ChromaDB
    CHROMA_DB_PATH: str = "./chroma_db"

    # Storage
    UPLOAD_PATH: str = "./uploads"
    GENERATED_FILES_PATH: str = "./generated_files"

    # Email
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_USERNAME: str = ""
    EMAIL_PASSWORD: str = ""
    EMAIL_FROM_NAME: str = "AI Job Agent"

    # App
    APP_ENV: str = "development"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    FRONTEND_URL: str = "http://localhost:3000"
    ALGORITHM: str = "HS256"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()