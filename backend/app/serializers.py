"""Row → dict serializers for API responses."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _clean(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode(errors="replace")
    return v


def to_dict(row: Any, exclude: set[str] | None = None) -> dict | None:
    if row is None:
        return None
    exclude = exclude or set()
    out: dict = {}
    for c in row.__table__.columns:
        if c.name in exclude:
            continue
        out[c.name] = _clean(getattr(row, c.name))
    return out


def rows_to_dicts(rows: list, exclude: set[str] | None = None) -> list[dict]:
    return [d for d in (to_dict(r, exclude) for r in rows) if d is not None]
