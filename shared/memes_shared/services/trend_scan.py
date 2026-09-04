"""Trend Hunter orchestration: score → rules → pipeline (no manual approval)."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from memes_shared.logging_setup import get_logger
from memes_shared.models import (
    AutomationLog,
    ContentSource,
    DiscoveredContent,
    PublishingJob,
    TrendHistory,
    TrendScore,
)
from memes_shared.services import rule_engine, trend_engine
from memes_shared.services.settings import get_setting
from memes_shared.services.notifier import notify_admins
from memes_shared.utils.timeutil import utcnow

log = get_logger("memes.trendhunter")

# checks whose failure is permanent → content marked 'skipped'
HARD_CHECKS = {"authorized_source", "category_allowed", "keywords_not_blocked",
               "keywords_allowed", "is_video"}
# soft checks (score/engagement/age/daily-cap) → keep 'detected' for re-scoring
SOFT_CHECKS = {"trend_score", "min_engagement", "max_age", "daily_cap"}


def run_trend_scan(session: Session, limit: int = 50) -> dict:
    """Score every unscored 'detected' item; apply automatic rules."""
    trend_cfg = get_setting(session, "trend")
    rules_cfg = get_setting(session, "rules")
    notif_cfg = get_setting(session, "notifications")
    discovery_cfg = get_setting(session, "discovery")

    max_age_filter = float(discovery_cfg.get("max_age_filter_hours", 72))
    now = utcnow()

    rows = (
        session.query(DiscoveredContent)
        .filter(DiscoveredContent.status == "detected")
        .outerjoin(TrendScore, TrendScore.content_id == DiscoveredContent.id)
        .filter(TrendScore.id.is_(None))
        .order_by(DiscoveredContent.discovered_at.desc())
        .limit(limit)
        .all()
    )
    scored = approved = rejected = skipped = 0
    hot_notifications: list[str] = []

    published_today = (
        session.query(func.count(PublishingJob.id))
        .filter(func.date(PublishingJob.created_at) == now.date())
        .scalar() or 0
    )

    for content in rows:
        # hard age filter at discovery level
        if content.published_at and (now - content.published_at) > timedelta(hours=max_age_filter):
            content.status = "skipped"
            content.error = f"older than {max_age_filter}h discovery window"
            skipped += 1
            continue

        source = session.get(ContentSource, content.source_id) if content.source_id else None
        history_rows = (
            session.query(TrendHistory)
            .filter(TrendHistory.content_id == content.id)
            .order_by(TrendHistory.captured_at)
            .all()
        )
        history = [
            {"engagement": h.engagement, "captured_at": h.captured_at.isoformat()}
            for h in history_rows
        ]
        score, breakdown = trend_engine.compute_trend_score(
            content.raw_metrics or {},
            content.published_at,
            source_stats={
                "success_count": source.success_count if source else 0,
                "error_count": source.error_count if source else 0,
            },
            trend_cfg=trend_cfg,
            history=history,
            now=now,
        )

        # persist score + history (upsert)
        ts = session.query(TrendScore).filter(TrendScore.content_id == content.id).first()
        if ts is None:
            ts = TrendScore(content_id=content.id)
            session.add(ts)
        ts.score = score
        ts.signals = breakdown
        ts.computed_at = now
        session.add(
            TrendHistory(content_id=content.id, score=score,
                         engagement=float(breakdown.get("engagement", 0)), captured_at=now)
        )
        scored += 1

        if score >= float(notif_cfg.get("trend_hot_min_score", 90)):
            hot_notifications.append(f"🔥 {score}/100 — {(content.title or content.url)[:80]}")

        decision = rule_engine.evaluate_rules(
            trend_score=score,
            metrics=content.raw_metrics or {},
            published_at=content.published_at,
            source_authorization=(source.authorization if source else "not_authorized"),
            category=content.category,
            title=content.title,
            description=content.description,
            media_type=content.media_type,
            cfg=rules_cfg,
            published_today=published_today,
            now=now,
        )
        content.raw_metrics = {**(content.raw_metrics or {}), "rule_decision": {
            "approved": decision.approved, "reasons": decision.reasons,
            "checks": decision.checks, "trend_score": score,
        }}

        if decision.approved:
            content.status = "processing"  # pipeline picks it up immediately
            approved += 1
            published_today += 1
            from memes_shared.services.pipeline import process_content

            process_content(session, content)
        else:
            failed_hard = [c for c, ok in decision.checks.items() if not ok and c in HARD_CHECKS]
            if failed_hard:
                content.status = "skipped"
                content.error = decision.reason_text[:1500]
                skipped += 1
            else:
                content.status = "detected"  # re-score later (soft failure)
                content.error = f"awaiting threshold: {decision.reason_text[:500]}"
                rejected += 1

    run_id = f"trend_{now.strftime('%Y%m%d%H%M%S')}"
    session.add(
        AutomationLog(
            run_id=run_id,
            job_name="trend_scan",
            status="success",
            message=f"scored {scored}, approved {approved}, rejected {rejected}, skipped {skipped}",
            items_processed=scored,
            started_at=now,
            finished_at=utcnow(),
        )
    )
    for note in hot_notifications[:5]:
        notify_admins(f"🔥 HIGH TREND SCORE DETECTED\n{note}", session=session)
    log.info("trend scan: %d scored / %d approved", scored, approved)
    return {"scored": scored, "approved": approved, "rejected": rejected, "skipped": skipped}
