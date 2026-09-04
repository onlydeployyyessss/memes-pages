"""Global settings stored in the DB (app_settings), merged over defaults."""
from __future__ import annotations

from sqlalchemy.orm import Session

from memes_shared.models import AppSetting

DEFAULT_SETTINGS: dict[str, dict] = {
    # Automation runtime state
    "automation": {
        "enabled": False,
        "paused": False,
        "stopped": False,
        "stop_reason": "",
        "run_requested": False,
        "last_run": None,
        "last_run_job": None,
    },
    # ── Automatic rule engine ────────────────────────────────────────
    "rules": {
        "min_trend_score": 85,          # 0..100
        "min_engagement": 100,          # likes+comments+shares
        "max_age_hours": 24,
        "allowed_categories": [],       # [] = all categories allowed
        "allowed_keywords": [],
        "blocked_keywords": [],
        "max_videos_per_day": 30,       # global automation cap
        "require_authorized_source": True,
        "require_video_media": True,
    },
    # ── Batch scheduler ──────────────────────────────────────────────
    "scheduler": {
        "batch_size": 10,
        "initial_delay_minutes": 60,
        "min_delay_minutes": 1,
        "max_delay_minutes": 5,
        "fixed_delay_minutes": 0,       # >0 → fixed gap, overrides min/max
        "rest_period_minutes": 330,     # 5.5 h rest between batches
        "max_posts_per_day": 24,
        "post_window_start": 8,         # local hour
        "post_window_end": 23,
        "quiet_hours_start": None,      # local hour (None = disabled)
        "quiet_hours_end": None,
        "timezone": "UTC",
    },
    # ── Trend Hunter scoring ─────────────────────────────────────────
    "trend": {
        "weights": {
            "views": 0.18, "likes": 0.13, "comments": 0.08, "shares": 0.10,
            "engagement_rate": 0.08, "growth_rate": 0.16, "velocity": 0.07,
            "freshness": 0.15, "source_history": 0.05,
        },
        "normalize_views": 250_000,
        "normalize_likes": 25_000,
        "normalize_comments": 2_000,
        "normalize_shares": 5_000,
        "max_engagement_rate": 0.15,        # ≥15% engagement rate scores full
        "growth_full_at_percent": 150.0,    # ≥150%/hour scores full
        "freshness_half_life_hours": 6,
        "max_age_hours": 72,                # older content scores 0 freshness
        "default_source_history": 0.7,
    },
    # ── Publishing ───────────────────────────────────────────────────
    "publishing": {
        # "dry_run" simulates publishing end-to-end without touching real
        # platforms; "live" uses official platform APIs per account.
        "mode": "dry_run",
        "backoff_base_minutes": 5,          # exponential backoff base
        "rate_limit_cooldown_minutes": 30,
        "notify_success": True,
        "notify_failed": True,
    },
    # ── Notifications ────────────────────────────────────────────────
    "notifications": {
        "trend_hot_min_score": 90,
        "milestone_follower_step": 1000,
        "notify_automation_errors": True,
        "daily_report_hour": 21,
    },
    # ── Discovery ────────────────────────────────────────────────────
    "discovery": {
        "agent_reach_enabled": False,   # never required — RSS works standalone
        "max_age_filter_hours": 72,     # ignore older items entirely
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def get_setting(session: Session, key: str) -> dict:
    row = session.get(AppSetting, key)
    stored = row.value if row else {}
    return _deep_merge(DEFAULT_SETTINGS.get(key, {}), stored or {})


def set_setting(session: Session, key: str, value: dict) -> dict:
    """Partially update a settings key (deep-merged over stored value)."""
    row = session.get(AppSetting, key)
    stored = (row.value if row else {}) or {}
    merged = _deep_merge(stored, value or {})
    if row is None:
        row = AppSetting(key=key, value=merged)
        session.add(row)
    else:
        row.value = merged
    session.flush()
    return merged


def ensure_default_settings(session: Session) -> None:
    for key in DEFAULT_SETTINGS:
        if session.get(AppSetting, key) is None:
            session.add(AppSetting(key=key, value=dict(DEFAULT_SETTINGS[key])))
    session.flush()


def get_all_settings(session: Session) -> dict[str, dict]:
    return {key: get_setting(session, key) for key in DEFAULT_SETTINGS}
