"""Automation runtime state — controlled from Telegram & Dashboard."""
from __future__ import annotations

from sqlalchemy.orm import Session

from memes_shared.models import (
    AutomationLog,
    PublishingJob,
)
from memes_shared.services.settings import get_setting, set_setting
from memes_shared.utils.timeutil import humanize_delta, utcnow


def get_state(session: Session) -> dict:
    return get_setting(session, "automation")


def start(session: Session) -> dict:
    return set_setting(session, "automation", {
        "enabled": True, "paused": False, "stopped": False, "stop_reason": "",
    })


def pause(session: Session) -> dict:
    return set_setting(session, "automation", {"paused": True})


def resume(session: Session) -> dict:
    return set_setting(session, "automation", {"paused": False})


def stop(session: Session, reason: str = "manual stop") -> dict:
    return set_setting(session, "automation", {"enabled": False, "stopped": True,
                                               "stop_reason": reason})


def request_run(session: Session) -> dict:
    return set_setting(session, "automation", {"run_requested": True})


def consume_run_request(session: Session) -> bool:
    state = get_state(session)
    if state.get("run_requested"):
        set_setting(session, "automation", {"run_requested": False})
        return True
    return False


def record_run(session: Session, job_name: str, message: str = "",
               items: int = 0, duration_ms: int = 0, run_id: str = "",
               status: str = "success") -> None:
    now = utcnow()
    session.add(
        AutomationLog(
            run_id=run_id or f"run_{now.strftime('%Y%m%d%H%M%S%f')}",
            job_name=job_name,
            status=status,
            message=message[:1900],
            items_processed=items,
            duration_ms=duration_ms,
            started_at=now,
            finished_at=now,
        )
    )
    set_setting(session, "automation", {"last_run": now.isoformat(), "last_run_job": job_name})


def status_summary(session: Session) -> dict:
    state = get_state(session)
    now = utcnow()
    queue_size = session.query(PublishingJob).filter(PublishingJob.status == "queued").count()
    scheduled = session.query(PublishingJob).filter(PublishingJob.status == "scheduled").count()
    active = (
        session.query(PublishingJob)
        .filter(PublishingJob.status.in_(["queued", "scheduled", "publishing"]))
        .count()
    )
    failed = session.query(PublishingJob).filter(PublishingJob.status == "failed").count()
    next_run = (
        session.query(PublishingJob)
        .filter(PublishingJob.status == "scheduled", PublishingJob.publish_at > now)
        .order_by(PublishingJob.publish_at)
        .first()
    )
    last_run = state.get("last_run")
    try:
        from datetime import datetime

        last_ago = (
            humanize_delta(now - datetime.fromisoformat(str(last_run)))
            if last_run else "never"
        )
    except Exception:  # noqa: BLE001
        last_ago = "never"
    return {
        "enabled": bool(state.get("enabled")),
        "paused": bool(state.get("paused")),
        "stopped": bool(state.get("stopped")),
        "stop_reason": state.get("stop_reason", ""),
        "label": (
            "🟢 Automation Running" if state.get("enabled") and not state.get("paused")
            else "⏸ Paused" if state.get("paused") and state.get("enabled")
            else "⏹ Stopped"
        ),
        "last_run": str(last_run or ""),
        "last_run_ago": last_ago,
        "last_run_job": state.get("last_run_job") or "",
        "next_run": next_run.publish_at.isoformat() if next_run and next_run.publish_at else "",
        "queue_size": queue_size,
        "scheduled_count": scheduled,
        "active_jobs": active,
        "failed_jobs": failed,
    }
