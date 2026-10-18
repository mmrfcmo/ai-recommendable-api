"""Application configuration using Pydantic Settings."""
from pydantic import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    app_name: str = "AI-Recommendable"
    app_version: str = "2.0.0"
    debug: bool = False

    database_url: Optional[str] = None

    jwt_secret_key: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 1440

    openai_api_key: Optional[str] = None
    google_places_api_key: Optional[str] = None
    brave_api_key: Optional[str] = None
    cors_origins: str = "*"

    gmail_email: Optional[str] = None
    gmail_app_password: Optional[str] = None

    @property
    def cors_origin_list(self) -> list:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        # Treat a wildcard configuration as a request for the known public frontends,
        # rather than returning "*" alongside allow_credentials=True. Starlette requires
        # explicit origins for credentialed CORS preflight requests.
        origins = [o for o in origins if o != "*"]
        # Keep existing configured origins and explicitly permit the RbAI Roofer
        # Edition frontends and isolated snapshot previews.
        required_origins = [
            "https://rbai-roofer-edition-staging.onrender.com",
            "https://rbai-roofer-edition-nav-preview.onrender.com",
            "https://rbai-roofer-snapshot-priority-preview.onrender.com",
            "https://rbai-roofer-snapshot-aha-v2-preview.onrender.com",
            "https://rbai-roofer-snapshot-v3-preview.onrender.com",
            "https://rbai-roofer-deep-dive-v3.onrender.com",
        ]
        return list(dict.fromkeys(origins + required_origins))

    @property
    def async_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        return "sqlite+aiosqlite:///./ai_recommendable.db"

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
