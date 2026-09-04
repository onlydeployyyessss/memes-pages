"""Automation / error / audit logs and global app settings."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from memes_shared.db.base import Base, BaseMixin, JSONType, utcnow


class AutomationLog(Base, BaseMixin):
    __tablename__ = "automation_logs"

    run_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    job_name: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), default="started")  # started|success|failed
    message: Mapped[str] = mapped_column(Text, default="")
    items_processed: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)


class ErrorLog(Base, BaseMixin):
    __tablename__ = "error_logs"

    scope: Mapped[str] = mapped_column(String(80), default="", index=True)
    error_type: Mapped[str] = mapped_column(String(120), default="")
    message: Mapped[str] = mapped_column(Text, default="")
    traceback: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[dict] = mapped_column(JSONType, default=dict)
    severity: Mapped[str] = mapped_column(String(20), default="error")
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)


class AIUsageLog(Base, BaseMixin):
    """One row per AI provider call (cost control + observability)."""

    __tablename__ = "ai_usage_logs"

    provider: Mapped[str] = mapped_column(String(40), default="openrouter", index=True)
    model: Mapped[str] = mapped_column(String(120), default="")
    feature: Mapped[str] = mapped_column(String(40), default="", index=True)
    # trend_analysis | captions | hashtags | categorize | language |
    # report_summary | assistant | test
    success: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    error_type: Mapped[str] = mapped_column(String(40), default="")
    error: Mapped[str] = mapped_column(Text, default="")


class AuditLog(Base, BaseMixin):
    __tablename__ = "audit_logs"

    actor_type: Mapped[str] = mapped_column(String(20), default="system")  # admin|bot|system
    actor_id: Mapped[str] = mapped_column(String(120), default="")
    action: Mapped[str] = mapped_column(String(120), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), default="")
    entity_id: Mapped[str] = mapped_column(String(120), default="")
    details: Mapped[dict] = mapped_column(JSONType, default=dict)
    ip: Mapped[str] = mapped_column(String(64), default="")


class AppSetting(Base):
    """Global key/value settings (rules, scheduler, trend weights, automation state)."""

    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
