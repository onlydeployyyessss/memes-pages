"""Automatic rule engine tests."""
from datetime import timedelta

from memes_shared.services.rule_engine import evaluate_rules
from memes_shared.utils.timeutil import utcnow


def _now():
    return utcnow()


def test_all_rules_pass():
    d = evaluate_rules(
        trend_score=92,
        metrics={"likes": 500, "comments": 100, "shares": 200},
        published_at=_now() - timedelta(hours=2),
        source_authorization="authorized",
        category="memes",
        title="funny cat meme",
        cfg={"min_trend_score": 85, "min_engagement": 100, "max_age_hours": 24,
             "allowed_categories": [], "blocked_keywords": [], "allowed_keywords": [],
             "max_videos_per_day": 10},
        published_today=0,
        now=_now(),
    )
    assert d.approved, d.reasons


def test_score_below_threshold_blocked_but_soft():
    d = evaluate_rules(
        trend_score=60, metrics={"likes": 10}, published_at=_now(),
        source_authorization="authorized", category="memes",
        cfg={"min_trend_score": 85}, now=_now(),
    )
    assert not d.approved
    assert d.checks["trend_score"] is False
    # no HARD check failed → candidate can be re-scored later
    hard_failures = [k for k, ok in d.checks.items()
                     if not ok and k in ("authorized_source", "category_allowed",
                                         "keywords_not_blocked", "keywords_allowed",
                                         "is_video")]
    assert not hard_failures, hard_failures


def test_unauthorized_source_is_hard_block():
    d = evaluate_rules(
        trend_score=99, metrics={"likes": 1000}, published_at=_now(),
        source_authorization="not_authorized", category="memes",
        cfg={"require_authorized_source": True}, now=_now(),
    )
    assert not d.approved
    assert d.checks["authorized_source"] is False


def test_blocked_keyword():
    d = evaluate_rules(
        trend_score=99, metrics={"likes": 1000}, published_at=_now(),
        source_authorization="authorized", category="memes",
        title="free crypto giveaway",
        cfg={"blocked_keywords": ["crypto", "giveaway"]}, now=_now(),
    )
    assert not d.approved
    assert d.checks["keywords_not_blocked"] is False


def test_daily_cap():
    d = evaluate_rules(
        trend_score=99, metrics={"likes": 1000}, published_at=_now(),
        source_authorization="authorized", category="memes",
        cfg={"max_videos_per_day": 5}, published_today=5, now=_now(),
    )
    assert not d.approved
    assert d.checks["daily_cap"] is False


def test_age_limit():
    d = evaluate_rules(
        trend_score=99, metrics={"likes": 1000},
        published_at=_now() - timedelta(hours=48),
        source_authorization="authorized", category="memes",
        cfg={"max_age_hours": 24}, now=_now(),
    )
    assert not d.approved
    assert d.checks["max_age"] is False
