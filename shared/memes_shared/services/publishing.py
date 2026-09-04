"""Multi-account publishing jobs: caption/cover resolution, dispatch loop."""
from __future__ import annotations

import json
import random
from datetime import timedelta

from sqlalchemy.orm import Session

from memes_shared.logging_setup import get_logger
from memes_shared.models import (
    AnalyticsEvent,
    Caption,
    CaptionTemplate,
    DestinationAccount,
    DiscoveredContent,
    PublishingBatch,
    PublishingHistory,
    PublishingJob,
    ReelCover,
    Video,
)
from memes_shared.services.captions import build_caption, pick_template
from memes_shared.services.settings import get_setting
from memes_shared.services.notifier import notify_admins
from memes_shared.utils.timeutil import utcnow

log = get_logger("memes.publishing")


# ── Caption / cover resolution ───────────────────────────────────────
def resolve_caption(session: Session, account: DestinationAccount, content: DiscoveredContent | None) -> tuple[str, int | None]:
    cs = account.settings.caption_settings if account.settings else {}
    cs = cs or {}
    mode = cs.get("mode", "default")
    hashtags = cs.get("hashtags") or []
    caption_row = session.get(Caption, account.default_caption_id) if account.default_caption_id else None
    template_row = session.get(CaptionTemplate, account.caption_template_id) if account.caption_template_id else None

    if mode == "template" and template_row is None:
        templates = session.query(CaptionTemplate).filter_by(enabled=True).all()
        template_row = pick_template(templates)
        mode = "template" if template_row else "default"

    context = {
        "title": (content.title if content else "") or "",
        "author": (content.author if content else "") or "",
        "source": (content.url if content else "") or "",
        "category": (content.category if content else "") or "",
        "account": account.username or account.name,
        "followers": account.followers_count,
    }
    text = build_caption(
        mode=mode,
        custom_text=cs.get("custom_text", ""),
        caption_row=caption_row,
        template_row=template_row,
        hashtags=hashtags,
        context=context,
        first_comment=cs.get("first_comment", ""),
    )
    return text, (caption_row.id if (mode == "default" and caption_row) else None)


def resolve_cover(session: Session, account: DestinationAccount) -> int | None:
    cs = (account.settings.cover_settings if account.settings else None) or {}
    mode = cs.get("mode", "account")
    if mode == "none":
        return None
    if mode == "account" and account.reel_cover_id:
        return account.reel_cover_id
    default_cover = session.query(ReelCover).filter_by(is_default=True).first()
    return default_cover.id if default_cover else account.reel_cover_id


def eligible_accounts(session: Session, content: DiscoveredContent) -> list[DestinationAccount]:
    """Accounts a video should be distributed to (multi-account distribution)."""
    target_ids = content.target_account_ids or []
    base = session.query(DestinationAccount).filter(
        DestinationAccount.status == "active",
        DestinationAccount.automation_enabled.is_(True),
    )
    if target_ids:
        return base.filter(DestinationAccount.id.in_(target_ids)).all()
    out = []
    for acc in base.all():
        dist = (acc.settings.distribution if acc.settings else None) or {}
        if dist.get("enabled") is False:
            continue
        cats = dist.get("categories") or []
        if cats and content.category not in cats:
            continue
        keywords = dist.get("keywords") or []
        if keywords:
            text = f"{content.title} {content.description}".lower()
            if not any(k.lower() in text for k in keywords):
                continue
        out.append(acc)
    return out


def create_jobs_for_content(session: Session, content: DiscoveredContent, video: Video | None) -> list[PublishingJob]:
    accounts = eligible_accounts(session, content)
    jobs: list[PublishingJob] = []
    delay_min = 0
    for account in accounts:
        dist = (account.settings.distribution if account.settings else None) or {}
        account_delay = int(dist.get("publish_delay_minutes", 0) or 0)
        text, caption_id = resolve_caption(session, account, content)
        cover_id = resolve_cover(session, account)
        job = PublishingJob(
            content_id=content.id,
            video_id=video.id if video else None,
            account_id=account.id,
            caption_id=caption_id,
            cover_id=cover_id,
            caption_text=text,
            job_type="short" if account.platform == "youtube"
            else ("reel" if account.platform == "instagram" else "video"),
            status="queued",
            priority=5,
        )
        session.add(job)
        jobs.append(job)
    if jobs:
        session.flush()
    return jobs


# ── Dispatch loop ────────────────────────────────────────────────────
def dispatch_due_jobs(session: Session, limit: int = 20, force_job_ids: list[int] | None = None) -> dict:
    """Publish all due jobs. Respects automation gate unless forced."""
    from memes_shared.services.publishers import get_publisher
    from memes_shared.security import decrypt_credential

    pub_cfg = get_setting(session, "publishing")
    mode = pub_cfg.get("mode", "dry_run")
    now = utcnow()

    query = session.query(PublishingJob).filter(
        PublishingJob.status.in_(["queued", "scheduled"]),
        (PublishingJob.publish_at.is_(None)) | (PublishingJob.publish_at <= now),
        (PublishingJob.next_retry_at.is_(None)) | (PublishingJob.next_retry_at <= now),
    )
    if force_job_ids:
        query = query.filter(PublishingJob.id.in_(force_job_ids))
    jobs = query.order_by(PublishingJob.priority, PublishingJob.publish_at).limit(limit).all()

    if not force_job_ids:
        auto = get_setting(session, "automation")
        if not auto.get("enabled") or auto.get("paused") or auto.get("stopped"):
            return {"dispatched": 0, "reason": "automation disabled"}

    stats = {"published": 0, "failed": 0, "skipped": 0, "rate_limited": False}
    aborted_account: int | None = None

    for job in jobs:
        if aborted_account == job.account_id:
            continue
        account = session.get(DestinationAccount, job.account_id)
        video = session.get(Video, job.video_id) if job.video_id else None
        if account is None or account.status != "active" or not account.automation_enabled:
            stats["skipped"] += 1
            continue
        if video is None or not video.file_path:
            job.status = "failed"
            job.last_error = "video file missing"
            stats["failed"] += 1
            _record_history(session, job, "failed", error=job.last_error)
            continue

        job.status = "publishing"
        session.flush()

        creds_json = decrypt_credential(account.credentials_enc) if account.credentials_enc else "{}"
        try:
            creds = json.loads(creds_json or "{}")
        except Exception:  # noqa: BLE001
            creds = {}

        effective_mode = mode
        if account.platform == "custom" or account.integration_status == "not_connected":
            effective_mode = "dry_run"

        publisher = get_publisher(account.platform if effective_mode == "live" else "dry_run")
        result = publisher.publish(
            video_path=video.file_path,
            caption=job.caption_text,
            cover_path=(session.get(ReelCover, job.cover_id).file_path if job.cover_id else video.cover_path or ""),
            account=account,
            job=job,
            creds=creds,
        )

        if result.success:
            job.status = "published"
            job.published_at = utcnow()
            account.last_publish_at = job.published_at
            session.add(
                AnalyticsEvent(
                    account_id=account.id, content_id=job.content_id, job_id=job.id,
                    event_type="publish_success", value=1, occurred_at=utcnow(),
                    meta={"publisher": publisher.name},
                )
            )
            _record_history(session, job, "published",
                            external_post_id=result.external_id, permalink=result.permalink,
                            response=result.raw)
            stats["published"] += 1
            _update_batch_counters(session, job, success=True)
            _maybe_content_published(session, job.content_id)
            if pub_cfg.get("notify_success", True):
                title = (session.get(DiscoveredContent, job.content_id).title if job.content_id else "") or "upload"
                notify_admins(
                    f"🟢 Publishing successful\n\n📱 @{account.username or account.name}\n🎬 {title[:100]}",
                    session=session,
                )
        else:
            job.attempts = (job.attempts or 0) + 1
            job.last_error = result.error[:1500]
            etype = result.error_type or "transient"
            _record_history(session, job, "failed", error=result.error, response=result.raw)
            session.add(
                AnalyticsEvent(
                    account_id=account.id, content_id=job.content_id, job_id=job.id,
                    event_type="publish_failed", value=1, occurred_at=utcnow(),
                    meta={"error_type": etype, "error": result.error[:300]},
                )
            )
            if etype == "rate_limit":
                # STOP publishing — cooldown + admin alert
                cooldown = int(pub_cfg.get("rate_limit_cooldown_minutes", 30))
                job.status = "scheduled"
                job.publish_at = utcnow() + timedelta(minutes=cooldown)
                account.status = "paused"
                stats["rate_limited"] = True
                aborted_account = account.id
                notify_admins(
                    f"⚠️ RATE LIMIT from platform for @{account.username or account.name}.\n"
                    f"Publishing paused for {cooldown} min. Job #{job.id} rescheduled.",
                    session=session,
                )
            elif etype == "auth":
                account.integration_status = "token_error"
                account.status = "error"
                job.status = "failed"
                notify_admins(
                    f"🔴 AUTHENTICATION ERROR for @{account.username or account.name}.\n"
                    f"Account paused — reconnect the integration in Settings.\nError: {result.error[:200]}",
                    session=session,
                )
            elif etype in ("config", "invalid"):
                job.status = "failed"
                notify_admins(
                    f"🔴 Publishing failed (permanent): job #{job.id} for @{account.username}\n{result.error[:300]}",
                    session=session,
                ) if pub_cfg.get("notify_failed", True) else None
            else:
                if job.attempts >= (job.max_attempts or 3):
                    job.status = "failed"
                    if pub_cfg.get("notify_failed", True):
                        notify_admins(
                            f"🔴 Publishing failed permanently: job #{job.id} @{account.username}\n{result.error[:300]}",
                            session=session,
                        )
                else:
                    # exponential backoff: base * 2^(attempt-1)
                    base = float(pub_cfg.get("backoff_base_minutes", 5))
                    delay = base * (2 ** (job.attempts - 1)) * (0.8 + 0.4 * random.random())
                    job.status = "scheduled"
                    job.next_retry_at = utcnow() + timedelta(minutes=delay)
                    log.info("job #%s transient failure, retry in %.1f min", job.id, delay)
            stats["failed"] += 1
            _update_batch_counters(session, job, success=False)

    session.flush()
    return stats


def _record_history(session: Session, job: PublishingJob, status: str, *,
                    external_post_id: str = "", permalink: str = "",
                    response: dict | None = None, error: str = "") -> None:
    session.add(
        PublishingHistory(
            job_id=job.id,
            account_id=job.account_id,
            content_id=job.content_id,
            status=status,
            external_post_id=external_post_id,
            permalink=permalink,
            published_at=utcnow() if status == "published" else None,
            response=response or {},
            error=error[:1500],
        )
    )


def _update_batch_counters(session: Session, job: PublishingJob, success: bool) -> None:
    if not job.batch_id:
        return
    batch = session.get(PublishingBatch, job.batch_id)
    if batch is None:
        return
    if success:
        batch.jobs_done = (batch.jobs_done or 0) + 1
    else:
        batch.jobs_failed = (batch.jobs_failed or 0) + 1
    if batch.jobs_done + batch.jobs_failed >= batch.jobs_total and batch.jobs_total:
        batch.status = "completed"
        batch.completed_at = utcnow()


def _maybe_content_published(session: Session, content_id: int | None) -> None:
    if content_id is None:
        return
    content = session.get(DiscoveredContent, content_id)
    if content is None:
        return
    remaining = (
        session.query(PublishingJob)
        .filter(PublishingJob.content_id == content_id,
                PublishingJob.status.notin_(["published", "cancelled", "skipped"]))
        .count()
    )
    if remaining == 0:
        content.status = "published"
