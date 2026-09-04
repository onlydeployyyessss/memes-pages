"""Batch scheduler math tests."""
from datetime import datetime, timedelta, timezone

from memes_shared.services.scheduler import plan_publish_times

CFG = {
    "batch_size": 3,
    "initial_delay_minutes": 60,
    "min_delay_minutes": 1,
    "max_delay_minutes": 5,
    "fixed_delay_minutes": 10,   # deterministic for tests
    "rest_period_minutes": 330,
    "max_posts_per_day": 0,      # unlimited for this test
    "post_window_start": 0,
    "post_window_end": 24,
    "quiet_hours_start": None,
    "quiet_hours_end": None,
    "timezone": "UTC",
}

START = datetime(2026, 9, 4, 10, 0, tzinfo=timezone.utc)


def test_initial_delay():
    plan = plan_publish_times(1, CFG, start=START)
    assert plan.times[0] == START + timedelta(minutes=60)


def test_fixed_gaps_within_batch():
    plan = plan_publish_times(3, CFG, start=START)
    t0, t1, t2 = plan.times
    assert t1 - t0 == timedelta(minutes=10)
    assert t2 - t1 == timedelta(minutes=10)


def test_rest_period_between_batches():
    plan = plan_publish_times(6, CFG, start=START)
    # 3rd job ends batch 1; job 4 (next batch's first) comes after the rest period
    gap = plan.times[3] - plan.times[2]
    assert gap == timedelta(minutes=330)
    assert any("rest" in e for e in plan.explanations)


def test_posting_window_shifts_to_next_day():
    cfg = {**CFG, "post_window_start": 9, "post_window_end": 18}
    start = datetime(2026, 9, 4, 17, 30, tzinfo=timezone.utc)
    plan = plan_publish_times(3, cfg, start=start)
    # first post ~18:30 (in window end 18? window = [9,18) → pushed to next day 09:00)
    assert plan.times[0].hour == 9, plan.times
    assert plan.times[0].day == 5


def test_quiet_hours_respected():
    cfg = {**CFG, "quiet_hours_start": 2, "quiet_hours_end": 8}
    start = datetime(2026, 9, 4, 6, 0, tzinfo=timezone.utc) + timedelta(minutes=60)
    plan = plan_publish_times(1, {**cfg, "initial_delay_minutes": 1}, start=start)
    assert not (2 <= plan.times[0].hour < 8), plan.times


def test_variable_gaps_bounded():
    cfg = {**CFG, "fixed_delay_minutes": 0, "min_delay_minutes": 2,
           "max_delay_minutes": 4, "batch_size": 10}
    plan = plan_publish_times(4, cfg, start=START)
    for a, b in zip(plan.times, plan.times[1:]):
        minutes = (b - a).total_seconds() / 60
        assert 2 <= minutes <= 4.001
