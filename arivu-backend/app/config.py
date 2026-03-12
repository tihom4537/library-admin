from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    port: int = 8001
    environment: str = "development"
    log_level: str = "debug"

    # Database (arivu's own PostgreSQL)
    database_url: str = "postgresql+asyncpg://arivu:arivu123@localhost:5432/arivu"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Whatomate bridge
    whatomate_base_url: str = "http://localhost:8080"
    whatomate_api_key: str = ""
    whatomate_webhook_secret: str = ""

    # Meta / WhatsApp Cloud API (for Flow messages)
    meta_phone_number_id: str = ""
    meta_access_token: str = ""
    meta_api_version: str = "v20.0"

    # Sarvam AI
    sarvam_api_key: str = ""
    sarvam_base_url: str = "https://api.sarvam.ai"

    # Admin portal — Auth (JWT)
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60
    jwt_refresh_token_expire_days: int = 30

    # Admin portal — AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    aws_s3_bucket: str = "arivu-kendra-media"

    # Admin portal — Gemini AI
    gemini_api_key: str = "AIzaSyAQHVs0Ax470luHep2hI4PDMLzmTYMp1Ms"
    gemini_model: str = "gemini-2.5-flash"


settings = Settings()
