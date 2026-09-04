"""Publishing queue: list, retry, cancel, reschedule."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.serializers import to_dict
from memes_shared.models import DestinationAccount, DiscoveredContent, PublishingJob
from memes_shared.services.scheduler import schedule_queue
from memes_shared.utils.timeutil import utcnow

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def list_jobs(
    status: str | None = None,
    account_id: int | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    q = (
        db.query(PublishingJob, DestinationAccount, DiscoveredContent)
        .join(DestinationAccount, DestinationAccount.id == PublishingJob.account_id)
        .outerjoin(DiscoveredContent, DiscoveredContent.id == PublishingJob.content_id)
        .order_by(PublishingJob.publish_at.is_(None), PublishingJob.publish_at, PublishingJob.id.desc())
    )
    if status:
        q = q.filter(PublishingJob.status == status)
    if account_id:
        q = q.filter(PublishingJob.account_id == account_id)
    total = q.count()
    rows = q.offset(offset).limit(min(limit, 200)).all()
    items = []
    for job, account, content in rows:
        d = to_dict(job, exclude={"caption_text"})
        d["caption"] = job.caption_text
        d["account_name"] = account.name
        d["account_username"] = account.username
        d["content_title"] = (content.title if content else "manual upload")[:80]
        items.append(d)
    return {"items": items, "total": total}


@router.post("/{job_id}/retry")
def retry_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(PublishingJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    job.status = "queued"
    job.attempts = 0
    job.next_retry_at = None
    job.last_error = ""
    job.publish_at = utcnow()
    db.commit()
    return to_dict(job)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(PublishingJob, job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    job.status = "cancelled"
    db.commit()
    return to_dict(job)


@router.post("/publish-now")
def publish_now(body: dict, db: Session = Depends(get_db)):
    """Force-dispatch specific job ids immediately (bypasses scheduler)."""
    ids = [int(x) for x in (body.get("job_ids") or [])]
    if not ids:
        raise HTTPException(422, "job_ids required")
    from memes_shared.services.publishing import dispatch_due_jobs

    stats = dispatch_due_jobs(db, limit=len(ids), force_job_ids=ids)
    db.commit()
    return stats


@router.post("/reschedule")
def reschedule(db: Session = Depends(get_db)):
    result = schedule_queue(db)
    db.commit()
    return result
