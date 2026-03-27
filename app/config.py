from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    app_name: str
    secret_key: str
    database_path: Path
    session_ttl_hours: int
    wb_base_url: str
    ozon_base_url: str
    http_timeout_seconds: float
    openrouter_api_key: str = ""
    llm_model: str = "mistralai/mistral-7b-instruct:free"

    @classmethod
    def from_env(cls) -> "Settings":
        database_path = Path(os.getenv("APP_DATABASE_PATH", "data/perenositsa.db"))
        return cls(
            app_name=os.getenv("APP_NAME", "Perenositsa"),
            secret_key=os.getenv("APP_SECRET_KEY", "unsafe-local-development-secret"),
            database_path=database_path,
            session_ttl_hours=int(os.getenv("APP_SESSION_TTL_HOURS", "24")),
            wb_base_url=os.getenv("WB_BASE_URL", "https://content-api.wildberries.ru").rstrip("/"),
            ozon_base_url=os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru").rstrip("/"),
            http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            llm_model=os.getenv("LLM_MODEL", "mistralai/mistral-7b-instruct:free"),
        )

