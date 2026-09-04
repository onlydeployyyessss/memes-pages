"""Batch scheduler settings & planned jobs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from memes_shared.models import DestinationAccount, PublishingJob
from memes_shared.services.scheduler import schedule_queue
from memes_shared.services.settings import get_setting, set_setting
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("/settings")
def get_schedule_settings(db: Session = Depends(get_db)):
    return get_setting(db, "scheduler")


@router.put("/settings")
def put_schedule_settings(body: dict, db: Session = Depends(get_db)):
    merged = set_setting(db, "scheduler", body)
    db.commit()
    return merged


@router.post("/recompute")
def recompute(db: Session = Depends(get_db)):
    result = schedule_queue(db)
    db.commit()
    return result


@router.get("/plan")
def plan(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(PublishingJob, DestinationAccount)
        .join(DestinationAccount, DestinationAccount.id == PublishingJob.account_id)
        .filter(PublishingJob.status == "scheduled")
        .order_by(PublishingJob.publish_at)
        .limit(min(limit, 200))
        .all()
    )
    items = []
    for job, account in rows:
        items.append({
            "job_id": job.id,
            "account": f"@{account.username or account.name}",
            "account_id": account.id,
            "publish_at": job.publish_at.isoformat() if job.publish_at else None,
            "batch_id": job.batch_id,
            "status": job.status,
            "content_title": (job.content.title if job.content else "upload")[:60],
        })
    return {"items": items, "total": len(items)}
