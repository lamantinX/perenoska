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
    yandex_market_base_url: str = "https://api.partner.market.yandex.ru"
    admin_emails: tuple[str, ...] = ()
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    catmatch_fuzzy_min: float = 75.0
    catmatch_embed_min: float = 0.82
    catmatch_llm_min: float = 60.0
    catmatch_llm_model: str = "openai/gpt-5.4-nano"
    catmatch_embed_model: str = "openai/text-embedding-3-small"
    catmatch_llm_batch_size: int = 15

    @classmethod
    def from_env(cls) -> "Settings":
        database_path = Path(os.getenv("APP_DATABASE_PATH", "data/perenositsa.db"))
        raw_admin_emails = os.getenv("ADMIN_EMAILS", "")
        admin_emails = tuple(
            e.strip().lower() for e in raw_admin_emails.split(",") if e.strip()
        )
        return cls(
            app_name=os.getenv("APP_NAME", "Perenositsa"),
            secret_key=os.getenv("APP_SECRET_KEY", "unsafe-local-development-secret"),
            database_path=database_path,
            session_ttl_hours=int(os.getenv("APP_SESSION_TTL_HOURS", "24")),
            wb_base_url=os.getenv("WB_BASE_URL", "https://content-api.wildberries.ru").rstrip("/"),
            ozon_base_url=os.getenv("OZON_BASE_URL", "https://api-seller.ozon.ru").rstrip("/"),
            yandex_market_base_url=os.getenv(
                "YANDEX_MARKET_BASE_URL",
                "https://api.partner.market.yandex.ru",
            ).rstrip("/"),
            http_timeout_seconds=float(os.getenv("HTTP_TIMEOUT_SECONDS", "30")),
            admin_emails=admin_emails,
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_base_url=os.getenv(
                "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"
            ).rstrip("/"),
            catmatch_fuzzy_min=float(os.getenv("CATMATCH_FUZZY_MIN", "75.0")),
            catmatch_embed_min=float(os.getenv("CATMATCH_EMBED_MIN", "0.82")),
            catmatch_llm_min=float(os.getenv("CATMATCH_LLM_MIN", "60.0")),
            catmatch_llm_model=os.getenv("CATMATCH_LLM_MODEL", "openai/gpt-5.4-nano"),
            catmatch_embed_model=os.getenv("CATMATCH_EMBED_MODEL", "openai/text-embedding-3-small"),
            catmatch_llm_batch_size=int(os.getenv("CATMATCH_LLM_BATCH_SIZE", "15")),
        )
