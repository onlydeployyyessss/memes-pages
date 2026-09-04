"""Caption & caption-template models."""
from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from memes_shared.db.base import Base, BaseMixin


class Caption(Base, BaseMixin):
    __tablename__ = "captions"

    name: Mapped[str] = mapped_column(String(160))
    text: Mapped[str] = mapped_column(Text, default="")
    hashtags: Mapped[list] = mapped_column(JSON, default=list)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(10), default="en")


class CaptionTemplate(Base, BaseMixin):
    """Template with placeholders: {title}, {author}, {source}, {hashtags}, {emoji} …"""

    __tablename__ = "caption_templates"

    name: Mapped[str] = mapped_column(String(160))
    template_text: Mapped[str] = mapped_column(Text, default="")
    placeholder_keys: Mapped[list] = mapped_column(JSON, default=list)
    weight: Mapped[int] = mapped_column(Integer, default=1)  # random-selection weight
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
