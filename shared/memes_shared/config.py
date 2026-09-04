"""Application configuration via environment variables (prefix ``MEMES_``)."""
from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MEMES_", env_file=".env", extra="ignore"
    )

    # Core
    env: str = "development"
    secret_key: str = "dev-secret-change-me-0123456789abcdef-memes-pages"
    log_level: str = "INFO"

    # Database
    database_url: str = ""
    sqlite_fallback: bool = True

    # Redis (optional)
    redis_url: str = ""

    # Admin bootstrap
    admin_email: str = "admin@memespages.local"
    admin_password: str = "change-me-strong-password"

    # Telegram
    bot_token: str = ""
    admin_telegram_ids: str = ""
    webhook_url: str = ""
    webhook_secret: str = ""

    # Media
    media_dir: str = "./media"
    public_media_base_url: str = ""

    # Encryption key for destination-account credentials at rest
    credential_encryption_key: str = ""

    # API rate limit (simple "N/period" format)
    api_rate_limit: str = "120/minute"

    # Agent-Reach (optional discovery provider)
    agent_reach_enabled: bool = False
    agent_reach_bin: str = "agent-reach"

    # OpenRouter (AI provider) — key never leaves the server
    openrouter_api_key: str = ""
    openrouter_model: str = "minimax/minimax-m3:free"
    openrouter_max_tokens: int = 1000
    openrouter_timeout: int = 30

    # ── Derived ──────────────────────────────────────────────────────
    @property
    def effective_database_url(self) -> str:
        url = self.database_url.strip()
        if url:
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            if url.startswith("postgresql://") and "sslmode" not in url:
                sep = "&" if "?" in url else "?"
                url = f"{url}{sep}sslmode=require"
            return url
        if self.sqlite_fallback:
            return "sqlite:///./data/memes_pages.db"
        print("FATAL: MEMES_DATABASE_URL is required when MEMES_SQLITE_FALLBACK=false", file=sys.stderr)
        raise SystemExit(1)

    @property
    def is_postgres(self) -> bool:
        return self.effective_database_url.startswith("postgresql")

    @property
    def admin_ids(self) -> list[int]:
        return [
            int(x)
            for x in self.admin_telegram_ids.replace(" ", "").split(",")
            if x.strip().isdigit()
        ]

    @property
    def media_path(self) -> Path:
        p = Path(self.media_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
