from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = "CareLink Emergency Bridge"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./carelink.db")
    secret_key: str = os.getenv("SECRET_KEY", "carelink-dev-only-change-me")
    allowed_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    )
    environment: str = os.getenv("ENVIRONMENT", "development")


settings = Settings()

if settings.environment == "production" and settings.secret_key == "carelink-dev-only-change-me":
    raise RuntimeError("Set SECRET_KEY to a secure value before starting in production.")
