"""Trend Hunter — trend score computation (0..100).

Signals considered: views, likes, comments, shares, engagement rate,
engagement growth rate, content age, posting time and source history.
All weights/normalizers are configurable via the `trend` settings key.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Any

from memes_shared.utils.timeutil import utcnow

ENGINE_VERSION = "v1"

# Fallback when no trend settings are provided (tests / CLI use)
DEFAULT_WEIGHTS = {
    "views": 0.18, "likes": 0.13, "comments": 0.08, "shares": 0.10,
    "engagement_rate": 0.08, "growth_rate": 0.16, "velocity": 0.07,
    "freshness": 0.15, "source_history": 0.05,
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_trend_score(
    metrics: dict[str, Any],
    published_at: datetime | None,
    source_stats: dict[str, Any] | None = None,
    trend_cfg: dict | None = None,
    history: list[dict] | None = None,
    now: datetime | None = None,
) -> tuple[float, dict]:
    """Return (score 0..100, breakdown dict).

    metrics: {"views","likes","comments","shares","growth_rate_percent_per_hour", ...}
    history: optional [{"engagement":float,"captured_at":iso}, ...] oldest→newest
    """
    cfg = {**{}, **(trend_cfg or {})}
    weights = cfg.get("weights") or DEFAULT_WEIGHTS
    views = float(metrics.get("views") or 0)
    likes = float(metrics.get("likes") or 0)
    comments = float(metrics.get("comments") or 0)
    shares = float(metrics.get("shares") or 0)
    now = now or utcnow()

    # ── Volume signals ───────────────────────────────────────────────
    s_views = _clamp01(views / max(1.0, float(cfg.get("normalize_views", 250_000))))
    s_likes = _clamp01(likes / max(1.0, float(cfg.get("normalize_likes", 25_000))))
    s_comments = _clamp01(comments / max(1.0, float(cfg.get("normalize_comments", 2_000))))
    s_shares = _clamp01(shares / max(1.0, float(cfg.get("normalize_shares", 5_000))))

    # ── Engagement rate ──────────────────────────────────────────────
    engagement = likes + comments + shares
    er = engagement / views if views > 0 else (0.05 if engagement > 0 else 0.0)
    s_er = _clamp01(er / max(0.01, float(cfg.get("max_engagement_rate", 0.15))))

    # ── Growth rate (% per hour): explicit metric or derived from history
    growth = metrics.get("growth_rate_percent_per_hour")
    derived_growth = 0.0
    if history and len(history) >= 2:
        try:
            t0 = datetime.fromisoformat(str(history[0]["captured_at"]).replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(str(history[-1]["captured_at"]).replace("Z", "+00:00"))
            hours = max(1e-6, (t1 - t0).total_seconds() / 3600.0)
            e0 = float(history[0].get("engagement") or 0)
            e1 = float(history[-1].get("engagement") or 0)
            if e0 > 0:
                derived_growth = max(0.0, (e1 - e0) / e0 * 100.0 / hours)
        except Exception:
            derived_growth = 0.0
    growth_rate = float(growth) if growth is not None else derived_growth
    s_growth = _clamp01(growth_rate / max(1.0, float(cfg.get("growth_full_at_percent", 150.0))))

    # ── Velocity: blends growth with how recent the surge is ─────────
    s_velocity = s_growth * 0.8 + s_er * 0.2

    # ── Freshness (content age, posting recency) ─────────────────────
    age_hours = 0.0
    if published_at is not None:
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=utcnow().tzinfo)
        age_hours = max(0.0, (now - published_at).total_seconds() / 3600.0)
    half_life = max(0.5, float(cfg.get("freshness_half_life_hours", 6)))
    max_age = float(cfg.get("max_age_hours", 72))
    freshness = 0.0 if age_hours > max_age else math.pow(0.5, age_hours / half_life)

    # ── Source history (authorization trust & reliability) ───────────
    src = source_stats or {}
    ok, err = int(src.get("success_count") or 0), int(src.get("error_count") or 0)
    s_source = (ok / (ok + err)) if (ok + err) > 0 else float(cfg.get("default_source_history", 0.7))

    parts = {
        "views": s_views * weights.get("views", 0),
        "likes": s_likes * weights.get("likes", 0),
        "comments": s_comments * weights.get("comments", 0),
        "shares": s_shares * weights.get("shares", 0),
        "engagement_rate": s_er * weights.get("engagement_rate", 0),
        "growth_rate": s_growth * weights.get("growth_rate", 0),
        "velocity": s_velocity * weights.get("velocity", 0),
        "freshness": freshness * weights.get("freshness", 0.0),
        "source_history": s_source * weights.get("source_history", 0),
    }
    score = round(sum(parts.values()) * 100.0, 1)
    score = max(0.0, min(100.0, score))

    breakdown = {
        "engine_version": ENGINE_VERSION,
        "score": score,
        "views": int(views),
        "likes": int(likes),
        "comments": int(comments),
        "shares": int(shares),
        "engagement": int(engagement),
        "engagement_rate": round(er, 4),
        "growth_rate_percent_per_hour": round(growth_rate, 2),
        "content_age_hours": round(age_hours, 2),
        "components": {k: round(v, 4) for k, v in parts.items() if v > 0},
    }
    return score, breakdown
