import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()


class Settings(BaseModel):
    app_name: str = "Conversation Agent"
    groq_api_key: str = Field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    groq_model: str = Field(
        default_factory=lambda: os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    )
    tavily_api_key: str = Field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))
    database_url: str = Field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite:///data/conversations.db"
        )
    )
    jwt_secret_key: str = Field(
        default_factory=lambda: os.getenv(
            "JWT_SECRET_KEY", "super-secret-production-jwt-key-2026-secure"
        )
    )
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440  # 24 Hours
    default_temperature: float = 0.0


settings = Settings()
