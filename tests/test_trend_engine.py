"""Trend Hunter scoring tests."""
from memes_shared.services.trend_engine import compute_trend_score


def test_viral_content_scores_high():
    metrics = {
        "views": 250_000, "likes": 30_000, "comments": 2_100, "shares": 5_000,
        "growth_rate_percent_per_hour": 150,
    }
    from datetime import timedelta

    from memes_shared.utils.timeutil import utcnow

    score, breakdown = compute_trend_score(
        metrics, utcnow() - timedelta(hours=2), trend_cfg=None, now=utcnow()
    )
    assert 80 <= score <= 100, f"expected hot score, got {score}"
    assert breakdown["engagement_rate"] > 0
    assert breakdown["components"]["growth_rate"] > 0


def test_dead_content_scores_low():
    from datetime import timedelta

    from memes_shared.utils.timeutil import utcnow

    score, _ = compute_trend_score(
        {"views": 10, "likes": 0, "comments": 0, "shares": 0},
        utcnow() - timedelta(hours=100),
        trend_cfg=None, now=utcnow(),
    )
    assert score < 15


def test_score_bounded():
    from datetime import timedelta

    from memes_shared.utils.timeutil import utcnow

    huge = {"views": 10**9, "likes": 10**8, "comments": 10**7, "shares": 10**7,
            "growth_rate_percent_per_hour": 10_000}
    score, _ = compute_trend_score(huge, utcnow() - timedelta(hours=1),
                                   trend_cfg=None, now=utcnow())
    assert 0 <= score <= 100


def test_history_growth():
    """Growth derived from trend history when no explicit metric exists."""
    from datetime import timedelta

    from memes_shared.utils.timeutil import utcnow

    now = utcnow()
    history = [
        {"engagement": 1000, "captured_at": (now - timedelta(hours=2)).isoformat()},
        {"engagement": 4000, "captured_at": now.isoformat()},
    ]
    _, breakdown = compute_trend_score(
        {"views": 50_000, "likes": 3_000, "comments": 300}, now - timedelta(hours=3),
        trend_cfg=None, history=history, now=now,
    )
    assert breakdown["growth_rate_percent_per_hour"] > 50
