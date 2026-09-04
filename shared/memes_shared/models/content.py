"""Discovered content, videos and video hashes (duplicate detection)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from memes_shared.db.base import Base, BaseMixin, JSONType


class DiscoveredContent(Base, BaseMixin):
    __tablename__ = "discovered_content"

    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("content_sources.id"), index=True
    )
    rss_feed_id: Mapped[int | None] = mapped_column(ForeignKey("rss_feeds.id"))
    external_id: Mapped[str] = mapped_column(String(255), default="", index=True)
    title: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="", index=True)
    media_url: Mapped[str] = mapped_column(Text, default="")
    media_type: Mapped[str] = mapped_column(String(20), default="video")
    thumbnail_url: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str] = mapped_column(String(160), default="")
    category: Mapped[str] = mapped_column(String(60), default="memes", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    raw_metrics: Mapped[dict] = mapped_column(JSONType, default=dict)
    # {"views":..,"likes":..,"comments":..,"shares":..} optionally refreshed
    status: Mapped[str] = mapped_column(String(20), default="detected", index=True)
    target_account_ids: Mapped[list] = mapped_column(JSONType, default=list)
    # empty list => all eligible accounts (multi-account distribution)
    error: Mapped[str] = mapped_column(Text, default="")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    videos: Mapped[list["Video"]] = relationship(back_populates="content", cascade="all, delete-orphan")


class Video(Base, BaseMixin):
    __tablename__ = "videos"

    content_id: Mapped[int] = mapped_column(
        ForeignKey("discovered_content.id"), index=True
    )
    file_path: Mapped[str] = mapped_column(Text, default="")  # stored (normalized) file
    original_path: Mapped[str] = mapped_column(Text, default="")
    cover_path: Mapped[str] = mapped_column(Text, default="")
    file_size: Mapped[int] = mapped_column(BigInteger, default=0)
    duration: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)
    format: Mapped[str] = mapped_column(String(20), default="mp4")
    fps: Mapped[float] = mapped_column(Float, default=0.0)
    has_audio: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    error: Mapped[str] = mapped_column(Text, default="")

    content: Mapped["DiscoveredContent | None"] = relationship(back_populates="videos")
    hashes: Mapped[list["VideoHash"]] = relationship(back_populates="video", cascade="all, delete-orphan")


class VideoHash(Base, BaseMixin):
    """Hashes used by the duplicate-detection system."""

    __tablename__ = "video_hashes"

    video_id: Mapped[int] = mapped_column(ForeignKey("videos.id"), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    phash: Mapped[str] = mapped_column(Text, default="")  # frame hashes joined by ':'
    phash_frames: Mapped[int] = mapped_column(Integer, default=0)
    source_url_hash: Mapped[str] = mapped_column(String(64), default="", index=True)

    video: Mapped["Video | None"] = relationship(back_populates="hashes")
