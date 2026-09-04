"""Time helpers."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone, tzinfo


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def humanize_delta(delta: timedelta) -> str:
    seconds = int(delta.total_seconds())
    if seconds < 0:
        return "just now"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {sec}s"
    return f"{sec}s"


def get_tzinfo(name: str | None) -> tzinfo:
    """Best-effort zoneinfo lookup, falls back to UTC."""
    if name:
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(name)
        except Exception:
            pass
    return timezone.utc


def minutes_since(dt: datetime, now: datetime | None = None) -> float:
    now = now or utcnow()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0.0, (now - dt).total_seconds() / 60.0)


def in_quiet_hours(
    now_local: datetime, quiet_start: int | None, quiet_end: int | None
) -> bool:
    """Quiet hours expressed as hours 0-23; supports ranges crossing midnight."""
    if quiet_start is None or quiet_end is None or quiet_start == quiet_end:
        return False
    h = now_local.hour
    if quiet_start < quiet_end:
        return quiet_start <= h < quiet_end
    return h >= quiet_start or h < quiet_end


def parse_hhmm(value: str | None) -> time | None:
    try:
        hh, mm = (value or "").split(":")
        return time(int(hh), int(mm))
    except Exception:
        return None
