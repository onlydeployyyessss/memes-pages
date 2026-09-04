"""Trending content (Trend Hunter output)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from memes_shared.models import (
    AnalyticsEvent,
    ContentSource,
    DiscoveredContent,
    PublishingHistory,
    TrendScore,
)
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.serializers import to_dict

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def list_trending(
    min_score: float = 0,
    status: str | None = None,
    category: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    q = (
        db.query(DiscoveredContent, TrendScore, ContentSource)
        .join(TrendScore, TrendScore.content_id == DiscoveredContent.id)
        .outerjoin(ContentSource, ContentSource.id == DiscoveredContent.source_id)
        .order_by(TrendScore.score.desc(), DiscoveredContent.discovered_at.desc())
        .limit(min(limit, 200))
    )
    if min_score > 0:
        q = q.filter(TrendScore.score >= min_score)
    if status:
        q = q.filter(DiscoveredContent.status == status)
    if category:
        q = q.filter(DiscoveredContent.category == category)
    rows = q.all()
    items = []
    for content, ts, source in rows:
        d = to_dict(content, exclude={"raw_metrics"})
        d["trend_score"] = ts.score if ts else None
        d["trend_signals"] = (ts.signals if ts else {}).get("components", {})
        d["ai_analysis"] = (ts.signals or {}).get("ai") if ts else None
        d["source_name"] = source.name if source else None
        d["source_authorization"] = source.authorization if source else None
        d["rule_decision"] = (content.raw_metrics or {}).get("rule_decision")
        items.append(d)
    return {"items": items, "total": len(items)}


@router.get("/{content_id}")
def trending_detail(content_id: int, db: Session = Depends(get_db)):
    content = db.get(DiscoveredContent, content_id)
    if content is None:
        raise HTTPException(404, "Content not found")
    ts = db.query(TrendScore).filter_by(content_id=content_id).first()
    d = to_dict(content)
    d["trend"] = to_dict(ts) if ts else None
    return d


@router.post("/{content_id}/disable-source")
def disable_source(content_id: int, db: Session = Depends(get_db)):
    content = db.get(DiscoveredContent, content_id)
    if content is None:
        raise HTTPException(404, "Content not found")
    if content.source_id is None:
        raise HTTPException(400, "Content has no source")
    src = db.get(ContentSource, content.source_id)
    src.enabled = False
    db.commit()
    return {"source_id": src.id, "enabled": False, "name": src.name}


@router.post("/{content_id}/queue")
def force_queue(content_id: int, db: Session = Depends(get_db)):
    """Manual override: push into the pipeline regardless of trend score."""
    content = db.get(DiscoveredContent, content_id)
    if content is None:
        raise HTTPException(404, "Content not found")
    from memes_shared.services.pipeline import process_content

    content.status = "processing"
    db.flush()
    result = process_content(db, content)
    db.commit()
    return {"content_id": content.id, "status": result}


@router.get("/{content_id}/analytics")
def content_analytics(content_id: int, db: Session = Depends(get_db)):
    content = db.get(DiscoveredContent, content_id)
    if content is None:
        raise HTTPException(404, "Content not found")
    events = (
        db.query(AnalyticsEvent)
        .filter(AnalyticsEvent.content_id == content_id)
        .order_by(AnalyticsEvent.occurred_at.desc())
        .limit(200)
        .all()
    )
    history = (
        db.query(PublishingHistory)
        .filter(PublishingHistory.content_id == content_id)
        .order_by(PublishingHistory.id.desc())
        .limit(50)
        .all()
    )
    return {
        "content": to_dict(content, exclude={"raw_metrics"}),
        "events": to_dict(events),
        "publishing": to_dict(history),
    }
