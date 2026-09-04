"""Batch publishing scheduler — spreads jobs over time, never simultaneous.

All values configurable: batch size, initial delay, min/max gap, fixed gap,
rest period between batches, posting window, quiet hours, max posts/day,
timezone.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from memes_shared.models import DestinationAccount, PublishingBatch, PublishingJob
from memes_shared.services.settings import get_setting
from memes_shared.utils.timeutil import get_tzinfo, in_quiet_hours, utcnow


@dataclass
class SchedulePlan:
    times: list[datetime] = field(default_factory=list)
    explanations: list[str] = field(default_factory=list)


def plan_publish_times(
    n_jobs: int,
    cfg: dict,
    start: datetime | None = None,
    account_day_counts: dict | None = None,
) -> SchedulePlan:
    """Pure scheduler math — deterministic inputs → deterministic plan.

    cfg keys: batch_size, initial_delay_minutes, min_delay_minutes,
    max_delay_minutes, fixed_delay_minutes, rest_period_minutes,
    max_posts_per_day, post_window_start, post_window_end,
    quiet_hours_start, quiet_hours_end, timezone
    """
    tz = get_tzinfo(cfg.get("timezone") or "UTC")
    now = (start or utcnow()).astimezone(tz)
    batch_size = max(1, int(cfg.get("batch_size", 10)))
    initial = float(cfg.get("initial_delay_minutes", 60))
    min_gap = float(cfg.get("min_delay_minutes", 1))
    max_gap = float(cfg.get("max_delay_minutes", 5))
    fixed_gap = float(cfg.get("fixed_delay_minutes", 0))
    rest = float(cfg.get("rest_period_minutes", 330))
    max_per_day = int(cfg.get("max_posts_per_day", 24))
    window_start = int(cfg.get("post_window_start", 0))
    window_end = int(cfg.get("post_window_end", 24))
    quiet_s = cfg.get("quiet_hours_start")
    quiet_e = cfg.get("quiet_hours_end")

    plan = SchedulePlan()
    t = now + timedelta(minutes=initial)
    day_key = None
    day_count = 0

    for i in range(n_jobs):
        if i > 0:
            if i % batch_size == 0:
                t = t + timedelta(minutes=rest)
                plan.explanations.append(
                    f"batch {(i // batch_size)} complete → rest {rest / 60:.1f} h"
                )
            else:
                gap = fixed_gap if fixed_gap > 0 else random.uniform(min_gap, max_gap)
                t = t + timedelta(minutes=gap)

        # move forward until inside posting window / outside quiet hours
        moved = 0
        while (window_start < window_end and not (window_start <= t.hour < window_end)) or \
              (window_start > window_end and not (t.hour >= window_start or t.hour < window_end)) or \
              in_quiet_hours(t, quiet_s, quiet_e):
            if window_start < window_end:
                if t.hour < window_start:
                    t = t.replace(hour=window_start, minute=0, second=0, microsecond=0)
                else:
                    t = (t + timedelta(days=1)).replace(
                        hour=window_start, minute=0, second=0, microsecond=0
                    )
            else:
                t = t + timedelta(hours=1)
            moved += 1
            if moved > 60:
                break

        # daily cap
        key = t.date()
        if key != day_key:
            day_key, day_count = key, 0
        if max_per_day > 0 and day_count >= max_per_day:
            t = (t + timedelta(days=1)).replace(
                hour=max(window_start, 0), minute=0, second=0, microsecond=0
            )
            day_key, day_count = t.date(), 0
        day_count += 1

        plan.times.append(t.astimezone(tz=None or __import__("datetime").timezone.utc))
    return plan


def schedule_queue(session: Session) -> dict:
    """Assign publish_at + batches to all unassigned queued jobs."""
    cfg = get_setting(session, "scheduler")
    jobs = (
        session.query(PublishingJob)
        .filter(PublishingJob.status == "queued", PublishingJob.publish_at.is_(None))
        .order_by(PublishingJob.priority, PublishingJob.id)
        .all()
    )
    if not jobs:
        return {"scheduled": 0, "batches": 0}

    # if a batch is resting, planning starts after the rest period
    start = utcnow()
    resting = (
        session.query(PublishingBatch)
        .filter(PublishingBatch.status.in_(["running", "resting"]))
        .order_by(PublishingBatch.id.desc())
        .first()
    )
    if resting is not None and resting.rest_until and resting.rest_until > start:
        start = resting.rest_until

    plan = plan_publish_times(len(jobs), cfg, start=start)
    batch_size = max(1, int(cfg.get("batch_size", 10)))
    batches: dict[int, PublishingBatch] = {}
    now = utcnow()

    for idx, (job, t) in enumerate(zip(jobs, plan.times)):
        batch_index = idx // batch_size
        if batch_index not in batches:
            batch = PublishingBatch(
                name=f"batch-{t.strftime('%Y%m%d-%H%M')}-{batch_index + 1}",
                status="planned",
                batch_size=batch_size,
                jobs_total=0,
                config=cfg,
                started_at=t,
            )
            session.add(batch)
            session.flush()
            batches[batch_index] = batch
        job.batch_id = batches[batch_index].id
        job.publish_at = t
        job.status = "scheduled"
        job.scheduled_at = now

    for batch in batches.values():
        count = sum(1 for j in jobs if j.batch_id == batch.id)
        batch.jobs_total = count
    session.flush()
    return {"scheduled": len(jobs), "batches": len(batches)}
