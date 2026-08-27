"""Application configuration using Pydantic Settings."""
from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "AI-Recommendable"
    app_version: str = "1.0.0"
    debug: bool = False

    database_url: Optional[str] = None

    jwt_secret_key: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440

    openai_api_key: Optional[str] = None
    google_places_api_key: Optional[str] = None
    cors_origins: str = "https://ai-recommendable.com,http://localhost:3000,http://localhost:5173"

    gmail_email: Optional[str] = None
    gmail_app_password: Optional[str] = None

    @property
    def cors_origin_list(self) -> list:
        origins = [o.strip() for o in self.cors_origins.split(",")]
        if "*" in origins:
            return ["*"]
        return origins

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return "sqlite+aiosqlite:///./ai_recommendable.db"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
