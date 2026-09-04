"""Analytics: overview KPIs, timeseries, account comparison, trends."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends
from memes_shared.models import (
    DailyMetric,
    DestinationAccount,
    DiscoveredContent,
    PublishingHistory,
    PublishingJob,
    TrendScore,
)
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db

router = APIRouter(dependencies=[Depends(current_admin)])


def _window(db: Session, days: int, offset_days: int = 0, account_id: int | None = None):
    from datetime import date

    today = date.today()
    start = today - timedelta(days=days + offset_days)
    stop = today - timedelta(days=offset_days)
    q = db.query(
        func.coalesce(func.sum(DailyMetric.views), 0),
        func.coalesce(func.sum(DailyMetric.likes + DailyMetric.comments + DailyMetric.shares), 0),
        func.coalesce(func.sum(DailyMetric.new_followers), 0),
        func.coalesce(func.sum(DailyMetric.posts), 0),
    ).filter(DailyMetric.date >= start, DailyMetric.date < stop)
    if account_id:
        q = q.filter(DailyMetric.account_id == account_id)
    return q.one()


@router.get("/overview")
def overview(db: Session = Depends(get_db)):
    accounts_total = db.query(func.count(DestinationAccount.id)).scalar() or 0
    accounts_active = (
        db.query(func.count(DestinationAccount.id))
        .filter(DestinationAccount.status == "active").scalar() or 0
    )
    detected = (
        db.query(func.count(DiscoveredContent.id)).scalar() or 0
    )
    queued = (
        db.query(func.count(PublishingJob.id))
        .filter(PublishingJob.status.in_(["queued", "scheduled"])).scalar() or 0
    )
    published = (
        db.query(func.count(PublishingJob.id))
        .filter(PublishingJob.status == "published").scalar() or 0
    )
    followers = (
        db.query(func.coalesce(func.sum(DestinationAccount.followers_count), 0))
        .filter(DestinationAccount.status != "disabled").scalar() or 0
    )
    now = _window(db, 7, 0)
    prev = _window(db, 7, 7)
    views7, eng7, newf7, posts7 = now
    views_prev, eng_prev, _, _ = prev
    er = (eng7 / views7 * 100) if views7 else 0.0
    er_prev = (eng_prev / views_prev * 100) if views_prev else 0.0
    growth = ((views7 - views_prev) / views_prev * 100) if views_prev else 0.0
    return {
        "total_accounts": accounts_total,
        "active_accounts": accounts_active,
        "videos_detected": detected,
        "videos_queued": queued,
        "videos_published": published,
        "total_views": int(views7),
        "total_followers": int(followers),
        "new_followers_7d": int(newf7),
        "engagement_rate": round(er, 2),
        "engagement_delta": round(er - er_prev, 2),
        "growth_rate": round(growth, 2),
        "posts_7d": int(posts7),
    }


@router.get("/timeseries")
def timeseries(days: int = 30, account_id: int | None = None,
               db: Session = Depends(get_db)):
    from datetime import date

    start = date.today() - timedelta(days=min(days, 180))
    q = (
        db.query(
            DailyMetric.date,
            func.coalesce(func.sum(DailyMetric.followers), 0),
            func.coalesce(func.sum(DailyMetric.new_followers), 0),
            func.coalesce(func.sum(DailyMetric.views), 0),
            func.coalesce(func.sum(DailyMetric.likes), 0),
            func.coalesce(func.sum(DailyMetric.comments), 0),
            func.coalesce(func.sum(DailyMetric.shares), 0),
            func.coalesce(func.sum(DailyMetric.posts), 0),
        )
        .filter(DailyMetric.date >= start)
        .group_by(DailyMetric.date)
        .order_by(DailyMetric.date)
    )
    if account_id:
        q = q.filter(DailyMetric.account_id == account_id)
    rows = q.all()
    return {
        "series": [
            {
                "date": r[0].isoformat(),
                "followers": int(r[1]),
                "new_followers": int(r[2]),
                "views": int(r[3]),
                "likes": int(r[4]),
                "comments": int(r[5]),
                "shares": int(r[6]),
                "posts": int(r[7]),
            }
            for r in rows
        ]
    }


@router.get("/comparison")
def comparison(db: Session = Depends(get_db)):
    from datetime import date

    start = date.today() - timedelta(days=30)
    rows = (
        db.query(
            DestinationAccount.id,
            DestinationAccount.name,
            DestinationAccount.username,
            DestinationAccount.followers_count,
            func.coalesce(func.sum(DailyMetric.views), 0),
            func.coalesce(func.sum(DailyMetric.likes + DailyMetric.comments + DailyMetric.shares), 0),
            func.coalesce(func.sum(DailyMetric.posts), 0),
        )
        .outerjoin(DailyMetric, (DailyMetric.account_id == DestinationAccount.id)
                   & (DailyMetric.date >= start))
        .group_by(DestinationAccount.id)
        .all()
    )
    out = []
    for r in rows:
        views, eng = int(r[4]), int(r[5])
        out.append({
            "account_id": r[0], "name": r[1], "username": r[2],
            "followers": int(r[3] or 0), "views_30d": views, "engagement_30d": eng,
            "posts_30d": int(r[6] or 0),
            "engagement_rate": round(eng / views * 100, 2) if views else 0.0,
        })
    out.sort(key=lambda x: x["views_30d"], reverse=True)
    return {"items": out}


@router.get("/trending-performance")
def trending_performance(limit: int = 20, db: Session = Depends(get_db)):
    rows = (
        db.query(DiscoveredContent, TrendScore, PublishingHistory)
        .join(TrendScore, TrendScore.content_id == DiscoveredContent.id)
        .outerjoin(PublishingHistory, PublishingHistory.content_id == DiscoveredContent.id)
        .order_by(TrendScore.score.desc())
        .limit(min(limit, 100))
        .all()
    )
    items = []
    seen = set()
    for content, ts, hist in rows:
        if content.id in seen:
            continue
        seen.add(content.id)
        items.append({
            "content_id": content.id,
            "title": (content.title or "")[:80],
            "trend_score": ts.score,
            "published_count": db.query(PublishingHistory)
                .filter(PublishingHistory.content_id == content.id,
                        PublishingHistory.status == "published").count(),
            "source_metrics": content.raw_metrics or {},
        })
    return {"items": items}
