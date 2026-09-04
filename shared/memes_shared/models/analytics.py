"""Analytics events and reports."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from memes_shared.db.base import Base, BaseMixin, JSONType


class AnalyticsEvent(Base, BaseMixin):
    __tablename__ = "analytics"

    account_id: Mapped[int | None] = mapped_column(
        ForeignKey("destination_accounts.id"), index=True
    )
    content_id: Mapped[int | None] = mapped_column(
        ForeignKey("discovered_content.id"), index=True
    )
    job_id: Mapped[int | None] = mapped_column(ForeignKey("publishing_jobs.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    value: Mapped[int] = mapped_column(BigInteger, default=0)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    meta: Mapped[dict] = mapped_column(JSONType, default=dict)


class Report(Base, BaseMixin):
    __tablename__ = "reports"

    report_type: Mapped[str] = mapped_column(String(20), index=True)  # ReportType
    title: Mapped[str] = mapped_column(String(255), default="")
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("destination_accounts.id"))
    text_content: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSONType, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="generated")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
