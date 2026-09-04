"""RSS feeds — creates the ContentSource + RssFeed pair."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.schemas import FeedIn
from backend.app.serializers import to_dict
from memes_shared.models import ContentSource, RssFeed
from memes_shared.services.discovery import discover_source

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def list_feeds(db: Session = Depends(get_db)):
    rows = db.query(RssFeed).order_by(RssFeed.priority, RssFeed.id).all()
    items = []
    for feed in rows:
        d = to_dict(feed)
        if feed.source:
            d["authorization"] = feed.source.authorization
            d["source_enabled"] = feed.source.enabled
        items.append(d)
    return {"items": items, "total": len(items)}


@router.post("", status_code=201)
def create_feed(body: FeedIn, db: Session = Depends(get_db)):
    src = ContentSource(
        name=body.feed_name,
        source_type="rss",
        url=body.url,
        authorization=body.authorization if body.authorization in ("authorized", "not_authorized", "disabled") else "authorized",
        enabled=body.enabled,
        categories=[body.category],
        priority=body.priority,
        check_interval_minutes=body.check_interval_minutes,
    )
    db.add(src)
    db.flush()
    feed = RssFeed(
        source_id=src.id,
        feed_name=body.feed_name,
        url=body.url,
        category=body.category,
        priority=body.priority,
        enabled=body.enabled,
        check_interval_minutes=body.check_interval_minutes,
    )
    db.add(feed)
    db.commit()
    return to_dict(feed)


@router.get("/{feed_id}")
def get_feed(feed_id: int, db: Session = Depends(get_db)):
    feed = db.get(RssFeed, feed_id)
    if feed is None:
        raise HTTPException(404, "Feed not found")
    d = to_dict(feed)
    d["authorization"] = feed.source.authorization if feed.source else None
    return d


@router.patch("/{feed_id}")
def patch_feed(feed_id: int, body: dict, db: Session = Depends(get_db)):
    feed = db.get(RssFeed, feed_id)
    if feed is None:
        raise HTTPException(404, "Feed not found")
    allowed_feed = {"feed_name", "category", "priority", "enabled",
                    "check_interval_minutes"}
    for field in allowed_feed & set(body):
        setattr(feed, field, body[field])
    if feed.source is not None:
        if "feed_name" in body:
            feed.source.name = body["feed_name"]
        if "priority" in body:
            feed.source.priority = body["priority"]
        if "enabled" in body:
            feed.source.enabled = bool(body["enabled"])
        if "check_interval_minutes" in body:
            feed.source.check_interval_minutes = body["check_interval_minutes"]
        if "authorization" in body and body["authorization"] in (
            "authorized", "not_authorized", "disabled"
        ):
            feed.source.authorization = body["authorization"]
        if "category" in body:
            feed.source.categories = [body["category"]]
    db.commit()
    return to_dict(feed)


@router.delete("/{feed_id}")
def delete_feed(feed_id: int, db: Session = Depends(get_db)):
    feed = db.get(RssFeed, feed_id)
    if feed is None:
        raise HTTPException(404, "Feed not found")
    if feed.source is not None:
        db.delete(feed.source)
    db.delete(feed)
    db.commit()
    return {"ok": True}


@router.post("/{feed_id}/check")
def check_feed_now(feed_id: int, db: Session = Depends(get_db)):
    feed = db.get(RssFeed, feed_id)
    if feed is None or feed.source is None:
        raise HTTPException(404, "Feed not found")
    created, skipped = discover_source(db, feed.source)
    db.commit()
    return {"feed_id": feed.id, "created": created, "skipped": skipped}
