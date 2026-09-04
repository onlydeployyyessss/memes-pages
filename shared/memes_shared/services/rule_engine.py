"""Automatic rule engine — no manual approval, configuration decides."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class RuleDecision:
    approved: bool
    reasons: list[str] = field(default_factory=list)
    checks: dict[str, bool] = field(default_factory=dict)

    @property
    def reason_text(self) -> str:
        return "; ".join(self.reasons) if self.reasons else "all rules passed"


def evaluate_rules(
    *,
    trend_score: float,
    metrics: dict[str, Any],
    published_at: datetime | None,
    source_authorization: str,
    category: str,
    title: str = "",
    description: str = "",
    media_type: str = "video",
    cfg: dict | None = None,
    published_today: int = 0,
    now: datetime | None = None,
) -> RuleDecision:
    """Evaluate automatic approval rules. Returns decision + human reasons."""
    cfg = cfg or {}
    from memes_shared.utils.timeutil import utcnow

    now = now or utcnow()
    checks: dict[str, bool] = {}
    reasons: list[str] = []

    min_score = float(cfg.get("min_trend_score", 85))
    ok_score = trend_score >= min_score
    checks["trend_score"] = ok_score
    if not ok_score:
        reasons.append(f"trend score {trend_score} < {min_score}")

    engagement = sum(float(metrics.get(k) or 0) for k in ("likes", "comments", "shares"))
    min_eng = float(cfg.get("min_engagement", 0))
    ok_eng = engagement >= min_eng
    checks["min_engagement"] = ok_eng
    if not ok_eng:
        reasons.append(f"engagement {int(engagement)} < {int(min_eng)}")

    max_age = float(cfg.get("max_age_hours", 24))
    age_h = 1e9 if published_at is None else max(
        0.0, (now - published_at).total_seconds() / 3600.0
    )
    if published_at is not None and published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=now.tzinfo)
        age_h = max(0.0, (now - published_at).total_seconds() / 3600.0)
    ok_age = age_h <= max_age
    checks["max_age"] = ok_age
    if not ok_age:
        reasons.append(
            f"content age {age_h:.1f}h > {max_age}h" if age_h < 1e8 else "content age unknown"
        )

    require_auth = bool(cfg.get("require_authorized_source", True))
    ok_auth = (not require_auth) or source_authorization == "authorized"
    checks["authorized_source"] = ok_auth
    if not ok_auth:
        reasons.append(f"source not authorized (status: {source_authorization})")

    # Category filter
    allowed_cats = [c.lower() for c in (cfg.get("allowed_categories") or [])]
    ok_cat = (not allowed_cats) or (category or "").lower() in allowed_cats
    checks["category_allowed"] = ok_cat
    if not ok_cat:
        reasons.append(f"category '{category}' not in allowed categories")

    # Keyword filters
    text = f"{title} {description}".lower()
    blocked = [k.lower() for k in (cfg.get("blocked_keywords") or [])]
    hit_blocked = [k for k in blocked if k and k in text]
    ok_blocked = not hit_blocked
    checks["keywords_not_blocked"] = ok_blocked
    if not ok_blocked:
        reasons.append(f"blocked keyword(s): {', '.join(hit_blocked[:5])}")

    allowed_kw = [k.lower() for k in (cfg.get("allowed_keywords") or [])]
    ok_kw = (not allowed_kw) or any(k and k in text for k in allowed_kw)
    checks["keywords_allowed"] = ok_kw
    if not ok_kw:
        reasons.append("no allowed keyword present")

    # Daily cap
    max_day = int(cfg.get("max_videos_per_day", 30))
    ok_day = published_today < max_day
    checks["daily_cap"] = ok_day
    if not ok_day:
        reasons.append(f"daily cap reached ({published_today}/{max_day})")

    # Media type
    if cfg.get("require_video_media", True):
        ok_media = media_type == "video"
        checks["is_video"] = ok_media
        if not ok_media:
            reasons.append(f"media type '{media_type}' is not video")

    return RuleDecision(approved=all(checks.values()), reasons=reasons, checks=checks)
