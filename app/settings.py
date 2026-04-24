from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("HDMAP_APP_NAME", "HDMap-Lab")
    cors_origins: tuple[str, ...] = tuple(
        origin.strip()
        for origin in os.getenv("HDMAP_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
        if origin.strip()
    )
    log_level: str = os.getenv("HDMAP_LOG_LEVEL", "INFO")


settings = Settings()

