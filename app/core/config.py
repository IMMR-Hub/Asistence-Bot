from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_ENV: Literal["development", "production", "test"] = "development"
    APP_PORT: int = 8000
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection string")

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # LLM Provider selection
    LLM_PROVIDER: Literal["groq", "ollama"] = "groq"

    # Generic LLM API (for OpenAI-compatible providers like Groq, Together, etc.)
    LLM_API_KEY: str = ""
    LLM_API_BASE: str = "https://api.groq.com/openai/v1"
    LLM_CLASSIFY_MODEL: str = "llama-3.1-8b-instant"  # Fast classification
    LLM_RESPONSE_MODEL: str = "llama-3.1-70b-versatile"  # Powerful responses
    LLM_TIMEOUT: int = 30

    # Fallback provider when primary fails
    LLM_FALLBACK_PROVIDER: Literal["ollama", "none"] = "ollama"

    # Ollama (local, used as fallback)
    OLLAMA_BASE_URL: str = "http://ollama:11434"
    OLLAMA_FALLBACK_MODEL: str = "qwen2.5:7b-instruct"
    OLLAMA_TIMEOUT: int = 60  # Ollama can be slow on CPU

    # WhatsApp
    WHATSAPP_PROVIDER: Literal["meta", "twilio"] = "meta"
    WHATSAPP_VERIFY_TOKEN: str = Field(default="changeme", description="Must be changed in production")
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    # Twilio optional
    TWILIO_ACCOUNT_SID_OPTIONAL: str | None = None
    TWILIO_AUTH_TOKEN_OPTIONAL: str | None = None
    TWILIO_WHATSAPP_NUMBER_OPTIONAL: str | None = None

    # Gmail optional
    GMAIL_CLIENT_ID_OPTIONAL: str | None = None
    GMAIL_CLIENT_SECRET_OPTIONAL: str | None = None
    GMAIL_REFRESH_TOKEN_OPTIONAL: str | None = None

    # SMTP optional
    SMTP_HOST_OPTIONAL: str | None = None
    SMTP_PORT_OPTIONAL: int = 587
    SMTP_USERNAME_OPTIONAL: str | None = None
    SMTP_PASSWORD_OPTIONAL: str | None = None
    SMTP_USE_TLS: bool = True

    # App
    DEFAULT_TIMEZONE: str = "UTC"
    RQ_QUEUE_NAME: str = "default"

    # Security
    API_SECRET_KEY: str = Field(default="change-this-in-production", description="Must be changed in production")
    WEBHOOK_SIGNATURE_VERIFY: bool = True

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v:
            raise ValueError("DATABASE_URL is required")
        return v

    @field_validator("API_SECRET_KEY", mode="after")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        import os
        if os.getenv("APP_ENV") == "production" and v == "change-this-in-production":
            raise ValueError("API_SECRET_KEY must be changed in production")
        return v

    @field_validator("WHATSAPP_VERIFY_TOKEN", mode="after")
    @classmethod
    def validate_verify_token(cls, v: str) -> str:
        import os
        if os.getenv("APP_ENV") == "production" and v == "changeme":
            raise ValueError("WHATSAPP_VERIFY_TOKEN must be changed in production")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
