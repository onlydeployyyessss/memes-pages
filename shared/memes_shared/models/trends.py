"""Trend scoring (Trend Hunter) models."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memes_shared.db.base import Base, BaseMixin, JSONType


class TrendScore(Base, BaseMixin):
    """Latest computed trend score for a piece of discovered content."""

    __tablename__ = "trend_scores"

    content_id: Mapped[int] = mapped_column(
        ForeignKey("discovered_content.id"), index=True, unique=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0..100
    signals: Mapped[dict] = mapped_column(JSONType, default=dict)
    engine_version: Mapped[str] = mapped_column(String(20), default="v1")
    computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    content: Mapped["DiscoveredContent | None"] = relationship(viewonly=True)  # noqa: F821 — registry-resolved


class TrendHistory(Base, BaseMixin):
    """Score over time — used for growth-rate / velocity calculations."""

    __tablename__ = "trend_history"

    content_id: Mapped[int] = mapped_column(
        ForeignKey("discovered_content.id"), index=True
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)
    engagement: Mapped[float] = mapped_column(Float, default=0.0)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
