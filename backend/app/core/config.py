import logging
import warnings
from pydantic_settings import BaseSettings
from pydantic import model_validator
from functools import lru_cache

logger = logging.getLogger(__name__)

_UNSAFE_DEFAULTS = {
    "change-me-in-production-use-openssl-rand-hex-32",
    "dev-secret-key-change-in-production",
    "change-me-n8n-callback-secret",
}


class Settings(BaseSettings):
    APP_NAME: str = "LLM Cloud Cost & Deployment Platform"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False  # Safe default — must opt-in to debug

    # Database (SQLite for local dev, PostgreSQL for production)
    DATABASE_URL: str = "sqlite+aiosqlite:///./llmplatform.db"
    DATABASE_URL_SYNC: str = "sqlite:///./llmplatform.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours (reduced from 24)
    ALGORITHM: str = "HS256"

    # Credential encryption (Fernet key — MUST be set in production)
    CREDENTIAL_ENCRYPTION_KEY: str = ""

    # CORS — comma-separated allowed origins
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:3001"

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

    # AI Agent
    AGENT_LLM_PROVIDER: str = "openai"  # "openai", "anthropic", "local"
    AGENT_LLM_API_KEY: str = ""
    AGENT_LLM_MODEL: str = "gpt-4o-mini"
    AGENT_LLM_BASE_URL: str = ""  # For local/custom endpoints

    # n8n Workflow
    N8N_WEBHOOK_URL: str = "http://localhost:5678/webhook/autonomous-llm-builder"
    N8N_CALLBACK_SECRET: str = "change-me-n8n-callback-secret"

    @model_validator(mode="after")
    def _warn_unsafe_secrets(self):
        """Refuse to start in production with insecure defaults."""
        if not self.DEBUG:
            if self.SECRET_KEY in _UNSAFE_DEFAULTS:
                raise ValueError(
                    "SECRET_KEY is still set to an insecure default. "
                    "Set a strong SECRET_KEY via environment variable or .env file."
                )
            if self.N8N_CALLBACK_SECRET in _UNSAFE_DEFAULTS:
                raise ValueError(
                    "N8N_CALLBACK_SECRET is still set to an insecure default. "
                    "Set a strong N8N_CALLBACK_SECRET via environment variable."
                )
        else:
            # In debug mode, warn but don't block
            if self.SECRET_KEY in _UNSAFE_DEFAULTS:
                warnings.warn(
                    "SECRET_KEY is insecure — acceptable for local dev only.",
                    stacklevel=2,
                )
        return self

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
