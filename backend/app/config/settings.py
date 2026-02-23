"""
Centralized configuration management using Pydantic Settings.
All environment variables are validated and accessed through this module.
"""
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Configuration
    ANTHROPIC_API_KEY: str = Field(..., description="Anthropic API key for Claude")
    ANTHROPIC_MODEL: str = Field(
        default="claude-sonnet-4-5",
        description="Claude model to use for conversations"
    )

    # Embeddings Configuration
    OPENAI_API_KEY: str = Field(..., description="OpenAI API key for embeddings")
    OPENAI_EMBEDDING_MODEL: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model"
    )

    # Vector Database Configuration
    PINECONE_API_KEY: str = Field(..., description="Pinecone API key")
    PINECONE_INDEX: str = Field(
        default="ivy-counsellor",
        description="Pinecone index name"
    )

    # Database Configuration
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/databases/ivy.db",
        description="SQLite database URL"
    )

    # Email Configuration (SendGrid)
    SENDGRID_API_KEY: str = Field(default="", description="SendGrid API key")
    ADMIN_EMAIL: str = Field(
        default="admin@ivyoverseas.com",
        description="Admin email for notifications"
    )

    # WhatsApp Configuration (optional)
    WHATSAPP_API_KEY: str = Field(default="", description="WhatsApp Business API key")
    WHATSAPP_PHONE_NUMBER: str = Field(default="", description="WhatsApp phone number")

    # Application Configuration
    DEBUG: bool = Field(default=False, description="Debug mode")
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    ENVIRONMENT: str = Field(default="development", description="Environment: development, staging, production")

    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"],
        description="Allowed CORS origins"
    )

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=60,
        description="Maximum requests per minute per IP"
    )

    # RAG Configuration
    RAG_TOP_K: int = Field(default=5, description="Number of documents to retrieve")
    RAG_SIMILARITY_THRESHOLD: float = Field(
        default=0.7,
        description="Minimum similarity score for RAG results"
    )

    # Intent Classification Thresholds
    HOT_LEAD_SCORE_THRESHOLD: int = Field(
        default=80,
        description="Score threshold for hot lead classification"
    )

    # Gap Report Configuration
    GAP_REPORT_SCHEDULE_HOUR: int = Field(
        default=9,
        description="Hour of day to send gap reports (24-hour format)"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    Uses lru_cache to ensure settings are loaded once and reused.
    """
    return Settings()


# Global settings instance
settings = get_settings()
