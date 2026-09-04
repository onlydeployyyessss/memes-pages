"""Content sources (authorization system) and RSS feeds."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memes_shared.db.base import Base, BaseMixin, JSONType


class ContentSource(Base, BaseMixin):
    """A discovery source with an explicit authorization status.

    Automation processes content ONLY from sources with authorization == 'authorized'.
    """

    __tablename__ = "content_sources"

    name: Mapped[str] = mapped_column(String(160))
    source_type: Mapped[str] = mapped_column(String(30), default="rss")  # SourceType
    url: Mapped[str] = mapped_column(Text, default="")
    authorization: Mapped[str] = mapped_column(String(20), default="not_authorized")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    categories: Mapped[list] = mapped_column(JSONType, default=list)
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1 (highest) .. 10
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    notes: Mapped[str] = mapped_column(Text, default="")
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)

    rss_feed: Mapped["RssFeed | None"] = relationship(
        back_populates="source", uselist=False, cascade="all, delete-orphan"
    )


class RssFeed(Base, BaseMixin):
    __tablename__ = "rss_feeds"

    source_id: Mapped[int] = mapped_column(
        ForeignKey("content_sources.id"), unique=True, index=True
    )
    feed_name: Mapped[str] = mapped_column(String(160))
    url: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(60), default="memes")
    priority: Mapped[int] = mapped_column(Integer, default=5)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    check_interval_minutes: Mapped[int] = mapped_column(Integer, default=15)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    etag: Mapped[str] = mapped_column(String(255), default="")
    last_modified: Mapped[str] = mapped_column(String(255), default="")
    items_seen: Mapped[int] = mapped_column(Integer, default=0)
    error_count: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")

    source: Mapped["ContentSource | None"] = relationship(back_populates="rss_feed")
