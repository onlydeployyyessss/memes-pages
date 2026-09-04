"""Memes Pages Agent — background worker entrypoint.

Runs the full automation loop:
  discovery → trend scan → pipeline → schedule → publish → metrics → reports

Safe to restart at any time: all state lives in PostgreSQL.
"""
from __future__ import annotations

import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from memes_shared.db.session import get_session
from memes_shared.logging_setup import get_logger, setup_logging
from memes_shared.services import automation, reports as reports_svc
from memes_shared.services.discovery import run_discovery_cycle
from memes_shared.services.metrics import refresh_all
from memes_shared.services.pipeline import process_pending
from memes_shared.services.publishing import dispatch_due_jobs
from memes_shared.services.scheduler import schedule_queue
from memes_shared.services.settings import get_setting
from memes_shared.services.trend_scan import run_trend_scan
from memes_shared.utils.timeutil import utcnow

setup_logging()
log = get_logger("memes.worker")

scheduler = BlockingScheduler(timezone="UTC")


def _enabled(session) -> bool:
    state = get_setting(session, "automation")
    return bool(state.get("enabled")) and not state.get("paused") and not state.get("stopped")


# ── Jobs ─────────────────────────────────────────────────────────────
def job_discovery():
    with get_session() as s:
        if not _enabled(s):
            return
        result = run_discovery_cycle(s)
        automation.record_run(s, "discovery", f"created {result['created']}",
                              items=result["created"])


def job_trend_scan():
    with get_session() as s:
        if not _enabled(s):
            return
        result = run_trend_scan(s)
        automation.record_run(s, "trend_scan",
                              f"scored {result['scored']}, approved {result['approved']}",
                              items=result["scored"])


def job_pipeline():
    with get_session() as s:
        result = process_pending(s)
        if result["processed"]:
            automation.record_run(s, "pipeline", f"processed {result['processed']}",
                                  items=result["processed"])


def job_schedule():
    with get_session() as s:
        if not _enabled(s):
            return
        result = schedule_queue(s)
        if result.get("scheduled"):
            automation.record_run(s, "schedule",
                                  f"scheduled {result['scheduled']} jobs in {result['batches']} batches")


def job_publish():
    with get_session() as s:
        # manual "run now" bypasses the automation gate
        run_now = automation.consume_run_request(s)
        stats = dispatch_due_jobs(s, limit=20)
        if run_now:
            # a forced run also drives discovery/scan/schedule once
            run_discovery_cycle(s)
            run_trend_scan(s)
            schedule_queue(s)
            automation.record_run(s, "run_now", "manual full cycle executed")
        s.commit()
        if stats.get("published") or stats.get("failed"):
            automation.record_run(
                s, "publish",
                f"published {stats.get('published', 0)}, failed {stats.get('failed', 0)}",
                items=stats.get("published", 0),
                status="failed" if stats.get("rate_limited") else "success",
            )


def job_metrics():
    with get_session() as s:
        results = refresh_all(s)
        automation.record_run(s, "metrics", f"refreshed {len(results)} accounts",
                              items=len(results))


def job_reports():
    with get_session() as s:
        produced = reports_svc.scheduled_reports(s)
        if produced:
            automation.record_run(s, "reports", f"generated: {', '.join(produced)}")


def job_cleanup():
    """Remove temp files older than 12h."""
    from pathlib import Path

    from memes_shared.config import get_settings

    tmp = get_settings().media_path / "tmp"
    now = utcnow().timestamp()
    removed = 0
    if tmp.exists():
        for f in tmp.iterdir():
            try:
                if f.is_file() and now - f.stat().st_mtime > 12 * 3600:
                    f.unlink()
                    removed += 1
            except OSError:
                continue
    if removed:
        with get_session() as s:
            automation.record_run(s, "cleanup", f"removed {removed} temp files")


def run_requested_check():
    """Fast tick: if an admin pressed Run Now, execute immediately."""
    with get_session() as s:
        if automation.consume_run_request(s):
            s.commit()
            log.info("run-now requested → executing full cycle")
            job_discovery()
            job_trend_scan()
            job_pipeline()
            job_schedule()
            job_publish()


# ── Wiring ───────────────────────────────────────────────────────────
def main() -> None:
    log.info("🤖 Memes Pages Agent worker starting…")
    scheduler.add_job(job_discovery, IntervalTrigger(minutes=5), id="discovery",
                      max_instances=1, coalesce=True)
    scheduler.add_job(job_trend_scan, IntervalTrigger(minutes=3), id="trend_scan",
                      max_instances=1, coalesce=True)
    scheduler.add_job(job_pipeline, IntervalTrigger(minutes=2), id="pipeline",
                      max_instances=1, coalesce=True)
    scheduler.add_job(job_schedule, IntervalTrigger(minutes=2), id="schedule",
                      max_instances=1, coalesce=True)
    scheduler.add_job(job_publish, IntervalTrigger(seconds=45), id="publish",
                      max_instances=1, coalesce=True)
    scheduler.add_job(run_requested_check, IntervalTrigger(seconds=20), id="run_now_check",
                      max_instances=1, coalesce=True)
    scheduler.add_job(job_metrics, IntervalTrigger(hours=6), id="metrics",
                      max_instances=1, coalesce=True)
    scheduler.add_job(job_reports, CronTrigger(hour=21, minute=5), id="reports",
                      max_instances=1, coalesce=True)
    scheduler.add_job(job_cleanup, CronTrigger(hour=4, minute=30), id="cleanup",
                      max_instances=1, coalesce=True)

    def _shutdown(signum, frame):  # noqa: ANN001
        log.info("worker stopping (signal %s)…", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    with get_session() as s:
        automation.record_run(s, "worker", "worker started")
    scheduler.start()


if __name__ == "__main__":
    main()
