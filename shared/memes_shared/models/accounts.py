"""Destination social accounts, per-account settings and metric samples."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memes_shared.db.base import Base, BaseMixin, JSONType


class DestinationAccount(Base, BaseMixin):
    __tablename__ = "destination_accounts"

    name: Mapped[str] = mapped_column(String(120))
    platform: Mapped[str] = mapped_column(String(30), default="instagram")  # Platform
    username: Mapped[str] = mapped_column(String(120), default="")
    external_id: Mapped[str] = mapped_column(String(120), default="")  # platform account id
    status: Mapped[str] = mapped_column(String(20), default="active")  # AccountStatus
    automation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    integration_status: Mapped[str] = mapped_column(String(30), default="not_connected")
    credentials_enc: Mapped[str] = mapped_column(Text, default="")  # encrypted JSON
    profile_pic_url: Mapped[str] = mapped_column(Text, default="")
    followers_count: Mapped[int] = mapped_column(BigInteger, default=0)
    last_publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Convenience FKs for default caption / template / cover
    default_caption_id: Mapped[int | None] = mapped_column(ForeignKey("captions.id"))
    caption_template_id: Mapped[int | None] = mapped_column(ForeignKey("caption_templates.id"))
    reel_cover_id: Mapped[int | None] = mapped_column(ForeignKey("reel_covers.id"))

    notes: Mapped[str] = mapped_column(Text, default="")

    settings: Mapped["AccountSettings | None"] = relationship(
        back_populates="account", uselist=False, cascade="all, delete-orphan"
    )


class AccountSettings(Base, BaseMixin):
    """Per-account caption / cover / schedule / limits configuration."""

    __tablename__ = "account_settings"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("destination_accounts.id"), unique=True, index=True
    )
    # caption: {"mode":"default|template|custom","custom_text":"","hashtags":[],"first_comment":""}
    caption_settings: Mapped[dict] = mapped_column(JSONType, default=dict)
    # cover: {"mode":"default|account|none","cover_id":null}
    cover_settings: Mapped[dict] = mapped_column(JSONType, default=dict)
    # schedule: {"post_window_start":9,"post_window_end":22,"quiet_start":null,"quiet_end":null,"timezone":"UTC"}
    schedule_settings: Mapped[dict] = mapped_column(JSONType, default=dict)
    # limits: {"max_per_day":10,"max_per_hour":3}
    posting_limits: Mapped[dict] = mapped_column(JSONType, default=dict)
    # distribution: {"enabled":true,"categories":[],"keywords":[],"publish_delay_minutes":0}
    distribution: Mapped[dict] = mapped_column(JSONType, default=dict)

    account: Mapped["DestinationAccount | None"] = relationship(back_populates="settings")


class AccountMetrics(Base, BaseMixin):
    """Point-in-time metric sample for an account."""

    __tablename__ = "account_metrics"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("destination_accounts.id"), index=True
    )
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    followers: Mapped[int] = mapped_column(BigInteger, default=0)
    following: Mapped[int] = mapped_column(BigInteger, default=0)
    posts_count: Mapped[int] = mapped_column(BigInteger, default=0)
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    likes: Mapped[int] = mapped_column(BigInteger, default=0)
    comments: Mapped[int] = mapped_column(BigInteger, default=0)
    shares: Mapped[int] = mapped_column(BigInteger, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    source: Mapped[str] = mapped_column(String(30), default="api")  # api|manual|import


class DailyMetric(Base, BaseMixin):
    """Aggregated per-account, per-day metrics for charts & reports."""

    __tablename__ = "daily_metrics"
    __table_args__ = (UniqueConstraint("account_id", "date", name="uq_daily_account_date"),)

    account_id: Mapped[int] = mapped_column(ForeignKey("destination_accounts.id"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    followers: Mapped[int] = mapped_column(BigInteger, default=0)
    new_followers: Mapped[int] = mapped_column(BigInteger, default=0)
    posts: Mapped[int] = mapped_column(BigInteger, default=0)
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    likes: Mapped[int] = mapped_column(BigInteger, default=0)
    comments: Mapped[int] = mapped_column(BigInteger, default=0)
    shares: Mapped[int] = mapped_column(BigInteger, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
