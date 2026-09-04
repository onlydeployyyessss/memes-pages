"""Publishing jobs, batches, history and schedule profiles."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memes_shared.db.base import Base, BaseMixin, JSONType


class PublishingJob(Base, BaseMixin):
    __tablename__ = "publishing_jobs"

    content_id: Mapped[int | None] = mapped_column(
        ForeignKey("discovered_content.id"), index=True
    )
    video_id: Mapped[int | None] = mapped_column(ForeignKey("videos.id"), index=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("destination_accounts.id"), index=True
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("publishing_batches.id"), index=True
    )
    caption_id: Mapped[int | None] = mapped_column(ForeignKey("captions.id"))
    cover_id: Mapped[int | None] = mapped_column(ForeignKey("reel_covers.id"))
    caption_text: Mapped[str] = mapped_column(Text, default="")
    job_type: Mapped[str] = mapped_column(String(20), default="reel")  # reel|short|video
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str] = mapped_column(Text, default="")

    content: Mapped["DiscoveredContent | None"] = relationship(viewonly=True)
    account: Mapped["DestinationAccount | None"] = relationship(viewonly=True)
    history: Mapped[list["PublishingHistory"]] = relationship(viewonly=True)


class PublishingBatch(Base, BaseMixin):
    __tablename__ = "publishing_batches"

    name: Mapped[str] = mapped_column(String(160), default="")
    status: Mapped[str] = mapped_column(String(20), default="planned", index=True)
    batch_size: Mapped[int] = mapped_column(Integer, default=10)
    jobs_total: Mapped[int] = mapped_column(Integer, default=0)
    jobs_done: Mapped[int] = mapped_column(Integer, default=0)
    jobs_failed: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rest_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config: Mapped[dict] = mapped_column(JSONType, default=dict)


class PublishingHistory(Base, BaseMixin):
    __tablename__ = "publishing_history"

    job_id: Mapped[int | None] = mapped_column(
        ForeignKey("publishing_jobs.id"), index=True
    )
    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("destination_accounts.id"), index=True
    )
    content_id: Mapped[int | None] = mapped_column(
        ForeignKey("discovered_content.id"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="published")
    external_post_id: Mapped[str] = mapped_column(String(255), default="")
    permalink: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    response: Mapped[dict] = mapped_column(JSONType, default=dict)
    error: Mapped[str] = mapped_column(Text, default="")


class Schedule(Base, BaseMixin):
    """A named batch-scheduling profile (all values configurable)."""

    __tablename__ = "schedules"

    name: Mapped[str] = mapped_column(String(160))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    applies_to: Mapped[list] = mapped_column(JSONType, default=list)  # account ids; [] = all
    config: Mapped[dict] = mapped_column(JSONType, default=dict)
    # config keys:
    #   batch_size, initial_delay_minutes, min_delay_minutes, max_delay_minutes,
    #   fixed_delay_minutes (0 = variable random), rest_period_minutes,
    #   max_posts_per_day, post_window_start, post_window_end,
    #   quiet_hours_start, quiet_hours_end, max_per_account_per_day
