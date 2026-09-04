"""Trend Hunter orchestration: score → rules → pipeline (no manual approval)."""
from __future__ import annotations

from datetime import timedelta

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
from memes_shared.services.ai import get_ai
from memes_shared.services.notifier import notify_admins
from memes_shared.services.settings import get_setting
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
    ai_cfg = get_setting(session, "ai")
    ai = get_ai(session)

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

        # ── OpenRouter AI analysis (optional — never blocks, never crashes) ──
        ai_data = None
        if ai.configured and ai_cfg.get("trend_assist"):
            try:
                meta = {
                    "title": (content.title or "")[:200],
                    "description": (content.description or "")[:400],
                    "category": content.category,
                    "source": source.name if source else "manual",
                    "source_authorization": source.authorization if source else None,
                    "views": breakdown.get("views", 0),
                    "likes": breakdown.get("likes", 0),
                    "comments": breakdown.get("comments", 0),
                    "shares": breakdown.get("shares", 0),
                    "engagement_rate": breakdown.get("engagement_rate", 0),
                    "growth_velocity_percent_per_hour": breakdown.get(
                        "growth_rate_percent_per_hour", 0),
                    "content_age_hours": breakdown.get("content_age_hours", 0),
                    "historical_source_performance": {
                        "successful_checks": source.success_count if source else 0,
                        "failed_checks": source.error_count if source else 0,
                    },
                }
                analysis = ai.analyze_trend(meta)
                if analysis is not None:
                    deterministic_score = score
                    ai_data = {
                        "trend_score": round(analysis.trend_score, 1),
                        "trend_level": analysis.trend_level,
                        "confidence": round(analysis.confidence, 2),
                        "category": analysis.category,
                        "reason": analysis.reason,
                        "recommendation": analysis.recommendation,
                        "model": ai.provider.model if ai.provider else "",
                    }
                    if ai_cfg.get("influence_scoring"):
                        # bounded blend — AI assists, deterministic engine anchors
                        weight = min(1.0, max(0.0, float(ai_cfg.get("blend_weight", 0.3))))
                        max_adj = float(ai_cfg.get("max_score_adjustment", 10.0))
                        blended = deterministic_score * (1 - weight) + analysis.trend_score * weight
                        score = round(
                            max(deterministic_score - max_adj,
                                min(deterministic_score + max_adj, blended)), 1)
                        ai_data["deterministic_score"] = deterministic_score
            except Exception as e:
                log.warning("AI trend analysis failed for #%s: %s", content.id, e)
        if ai_data is not None:
            breakdown["ai"] = ai_data

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
            note = f"🔥 {score}/100 — {(content.title or content.url)[:80]}"
            if ai_data and ai_data.get("reason"):
                note += f"\n🧠 {ai_data['reason'][:140]}"
            hot_notifications.append(note)

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
