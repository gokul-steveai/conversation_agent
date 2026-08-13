import os

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

load_dotenv()


class Settings(BaseModel):
    app_name: str = "AI Chat Assistant"
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development").lower()
    )
    allowed_origins: list[str] = Field(
        default_factory=lambda: (
            [origin.strip() for origin in origins_env.split(",") if origin.strip()]
            if (origins_env := os.getenv("ALLOWED_ORIGINS"))
            else [
                "http://localhost:8501",
                "http://127.0.0.1:8501",
                "http://localhost:3000",
            ]
        )
    )
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

    @model_validator(mode="after")
    def validate_cors_allowlist(self) -> "Settings":
        if self.environment != "development":
            if not self.allowed_origins or "*" in self.allowed_origins:
                raise ValueError(
                    "In non-development environments, ALLOWED_ORIGINS must be explicitly configured "
                    "with explicit non-wildcard origins when allow_credentials=True."
                )
        return self


settings = Settings()
