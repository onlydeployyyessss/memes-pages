"""Formatting helpers for bot messages."""
from __future__ import annotations

from datetime import datetime

from memes_shared.utils.timeutil import humanize_delta, utcnow

STATUS_EMOJI = {
    "detected": "🟡", "processing": "🔵", "queued": "🟣", "scheduled": "🟠",
    "published": "🟢", "failed": "🔴", "skipped": "⚪", "cancelled": "⚫",
    "active": "🟢", "paused": "⏸", "error": "🔴", "disabled": "⚫",
    "authorized": "🟢", "not_authorized": "🔴", "connected": "🟢",
    "not_connected": "⚪", "token_error": "🔴",
}


def st(status: str | None) -> str:
    return STATUS_EMOJI.get(status or "", "•")


def fmt_int(n: float | int | None) -> str:
    n = int(n or 0)
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def score_bar(score: float, width: int = 10) -> str:
    filled = round(max(0, min(100, score)) / 100 * width)
    return "█" * filled + "░" * (width - filled)


def trend_line(score: float, signals: dict) -> str:
    views = signals.get("views", 0)
    likes = signals.get("likes", 0)
    comments = signals.get("comments", 0)
    growth = signals.get("growth_rate_percent_per_hour", 0)
    age = signals.get("content_age_hours", 0)
    return (
        f"Trend Score: <b>{score:.0f}/100</b> 🔥\n"
        f"<code>{score_bar(score)}</code>\n\n"
        f"👁 Views: {fmt_int(views)}   ❤️ {fmt_int(likes)}   💬 {fmt_int(comments)}\n"
        f"📈 Growth: +{growth:.0f}%/hour\n"
        f"🕐 Content Age: {age:.0f}h"
    )


def ago(dt: datetime | None) -> str:
    if dt is None:
        return "never"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=utcnow().tzinfo)
    return humanize_delta(utcnow() - dt) + " ago"


def truncate(text: str | None, length: int = 60) -> str:
    text = text or ""
    return text if len(text) <= length else text[: length - 1] + "…"
