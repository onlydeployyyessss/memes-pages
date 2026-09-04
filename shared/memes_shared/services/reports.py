"""Automatic reports: daily / weekly / monthly / network / account."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from memes_shared.logging_setup import get_logger
from memes_shared.models import (
    DailyMetric,
    DestinationAccount,
    DiscoveredContent,
    PublishingHistory,
    Report,
)
from memes_shared.services.notifier import notify_admins
from memes_shared.services.settings import get_setting
from memes_shared.utils.timeutil import utcnow

log = get_logger("memes.reports")


def fmt_int(n: float) -> str:
    n = int(n or 0)
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


PERIODS = {"daily": 1, "weekly": 7, "monthly": 30}


def collect_period(session: Session, days: int, account_id: int | None = None):
    end = utcnow()
    start = end - timedelta(days=days)
    dm_q = session.query(
        func.coalesce(func.sum(DailyMetric.views), 0),
        func.coalesce(func.sum(DailyMetric.likes), 0),
        func.coalesce(func.sum(DailyMetric.comments), 0),
        func.coalesce(func.sum(DailyMetric.shares), 0),
        func.coalesce(func.sum(DailyMetric.new_followers), 0),
    ).filter(DailyMetric.date >= start.date(), DailyMetric.date <= end.date())
    if account_id:
        dm_q = dm_q.filter(DailyMetric.account_id == account_id)
    views, likes, comments, shares, new_followers = dm_q.one()

    ph_q = session.query(func.count(PublishingHistory.id)).filter(
        PublishingHistory.status == "published",
        PublishingHistory.published_at >= start,
    )
    if account_id:
        ph_q = ph_q.filter(PublishingHistory.account_id == account_id)
    published = ph_q.scalar() or 0

    detected = (
        session.query(func.count(DiscoveredContent.id))
        .filter(DiscoveredContent.discovered_at >= start).scalar() or 0
    )
    active_accounts = (
        session.query(func.count(DestinationAccount.id))
        .filter(DestinationAccount.status == "active").scalar() or 0
    )
    total_followers = (
        session.query(func.coalesce(func.sum(DestinationAccount.followers_count), 0))
        .filter(DestinationAccount.status != "disabled").scalar() or 0
    )

    # best account by views in period
    best = None
    best_row = (
        session.query(DailyMetric.account_id,
                      func.sum(DailyMetric.views).label("views"))
        .filter(DailyMetric.date >= start.date())
        .group_by(DailyMetric.account_id)
        .order_by(func.sum(DailyMetric.views).desc())
        .first()
    )
    if best_row and best_row.account_id:
        acc = session.get(DestinationAccount, best_row.account_id)
        if acc is not None:
            best = acc

    # engagement trend: last 7 days vs previous 7
    def _er(days_ago_start: int, days_ago_end: int) -> float:
        s = (end - timedelta(days=days_ago_start)).date()
        e = (end - timedelta(days=days_ago_end)).date()
        row = session.query(
            func.coalesce(func.sum(DailyMetric.likes + DailyMetric.comments + DailyMetric.shares), 0),
            func.coalesce(func.sum(DailyMetric.views), 0),
        ).filter(DailyMetric.date >= s, DailyMetric.date <= e)
        if account_id:
            row = row.filter(DailyMetric.account_id == account_id)
        eng, vw = row.one()
        return (float(eng) / float(vw) * 100.0) if vw else 0.0

    er_now = _er(7, 0)
    er_prev = _er(14, 7)
    er_delta = (er_now - er_prev) if er_prev else er_now

    return {
        "period_days": days, "published": published, "detected": detected,
        "views": int(views), "likes": int(likes), "comments": int(comments),
        "shares": int(shares), "new_followers": int(new_followers),
        "active_accounts": active_accounts, "total_followers": int(total_followers),
        "engagement_pct": round(er_now, 2), "engagement_delta_pct": round(er_delta, 2),
        "best_account": best.username if best else None,
    }


def build_report_text(title: str, d: dict) -> str:
    lines = [
        f"📊 {title}",
        "",
        f"Active Accounts: {d['active_accounts']}",
        f"Videos Published: {d['published']}",
        f"Total Views: {fmt_int(d['views'])}",
        f"New Followers: +{fmt_int(d['new_followers'])}",
        f"Engagement: {d['engagement_pct']}% ({'+' if d['engagement_delta_pct'] >= 0 else ''}{d['engagement_delta_pct']}%)",
    ]
    if d.get("best_account"):
        lines.append(f"\n🔥 Best Performing Account: @{d['best_account']}")
    return "\n".join(lines)


def generate_report(session: Session, report_type: str, account_id: int | None = None,
                    send: bool = True) -> Report:
    now = utcnow()
    days = PERIODS.get(report_type, 1)
    if report_type == "network":
        days = 7
    d = collect_period(session, days, account_id)
    account = session.get(DestinationAccount, account_id) if account_id else None
    label = {
        "daily": "MEMES PAGES DAILY REPORT",
        "weekly": "MEMES PAGES WEEKLY REPORT",
        "monthly": "MEMES PAGES MONTHLY REPORT",
        "network": "MEMES PAGES NETWORK REPORT",
        "account": f"ACCOUNT REPORT — @{account.username}" if account else "ACCOUNT REPORT",
    }.get(report_type, "MEMES PAGES REPORT")
    text = build_report_text(label, d)

    # ── Optional AI-written summary (from DB data only, never invented) ──
    try:
        from memes_shared.services.ai import get_ai

        ai = get_ai(session)
        if ai.configured and get_setting(session, "ai").get("report_summaries"):
            ai_summary = ai.summarize_report(text, d)
            if ai_summary:
                text = f"{text}\n\n{ai_summary}"
    except Exception as e:
        log.warning("AI report summary failed: %s", e)
    report = Report(
        report_type=report_type,
        title=label[:255],
        period_start=now - timedelta(days=days),
        period_end=now,
        account_id=account_id,
        text_content=text,
        payload=d,
        status="generated",
    )
    session.add(report)
    session.flush()
    if send:
        sent = notify_admins(text, session=session)
        report.status = "sent" if sent else "failed"
        report.sent_at = now if sent else None
    session.flush()
    return report


def scheduled_reports(session: Session) -> list[str]:
    """Run due daily/weekly/monthly reports (called by worker cron)."""
    cfg = get_setting(session, "notifications")
    produced = []
    for rtype in ("daily", "weekly", "monthly"):
        latest = (
            session.query(Report)
            .filter(Report.report_type == rtype)
            .order_by(Report.id.desc())
            .first()
        )
        due = (
            latest is None
            or latest.created_at is None
            or (utcnow() - latest.created_at).days >= {"daily": 1, "weekly": 7, "monthly": 30}[rtype]
        )
        if due:
            generate_report(session, rtype)
            produced.append(rtype)
    return produced
