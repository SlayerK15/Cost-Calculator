from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "LLM Cloud Cost & Deployment Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # Database (SQLite for local dev, PostgreSQL for production)
    DATABASE_URL: str = "sqlite+aiosqlite:///./llmplatform.db"
    DATABASE_URL_SYNC: str = "sqlite:///./llmplatform.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"

    # File Upload
    MAX_UPLOAD_SIZE_GB: int = 50
    UPLOAD_DIR: str = "/tmp/llm-uploads"
    S3_BUCKET: str = ""
    S3_REGION: str = "us-east-1"

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRO_PRICE_ID: str = ""       # price_xxx for Pro $49/mo
    STRIPE_ENTERPRISE_PRICE_ID: str = "" # price_xxx for Enterprise $199/mo
    FRONTEND_URL: str = "http://localhost:3000"

    # Hugging Face
    HF_TOKEN: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
