"""Account metrics refresh via official APIs (+ deterministic dry-run mode)."""
from __future__ import annotations

import hashlib
from datetime import date, timedelta

import httpx
from sqlalchemy.orm import Session

from memes_shared.logging_setup import get_logger
from memes_shared.models import (
    AccountMetrics,
    DailyMetric,
    DestinationAccount,
    PublishingHistory,
)
from memes_shared.security import decrypt_credential
from memes_shared.utils.timeutil import utcnow

log = get_logger("memes.metrics")


def _deterministic(account_id: int, day: date, salt: str, low: int, high: int) -> int:
    h = hashlib.sha256(f"{account_id}:{day.isoformat()}:{salt}".encode()).hexdigest()
    return low + int(h[:8], 16) % max(1, high - low)


def upsert_daily_metric(session: Session, account_id: int, day: date, **values) -> DailyMetric:
    row = (
        session.query(DailyMetric)
        .filter(DailyMetric.account_id == account_id, DailyMetric.date == day)
        .first()
    )
    if row is None:
        row = DailyMetric(account_id=account_id, date=day)
        session.add(row)
    for k, v in values.items():
        if hasattr(row, k):
            setattr(row, k, v)
    session.flush()
    return row


def refresh_account_metrics(session: Session, account: DestinationAccount) -> dict:
    """Pull followers/views/etc. from the official platform API.

    In dry-run mode (platform 'custom' or not connected) metrics are derived
    deterministically from real publishing history — clearly marked simulated.
    """
    now = utcnow()
    today = now.date()
    creds: dict = {}
    if account.credentials_enc:
        import json

        try:
            creds = json.loads(decrypt_credential(account.credentials_enc) or "{}")
        except Exception:
            creds = {}

    if account.platform == "instagram" and creds.get("access_token"):
        return _refresh_instagram(session, account, creds, now, today)
    if account.platform == "youtube" and (creds.get("access_token") or creds.get("refresh_token")):
        return _refresh_youtube(session, account, creds, now, today)

    # ── Dry-run / simulated metrics ──────────────────────────────────
    posts = (
        session.query(PublishingHistory)
        .filter(PublishingHistory.account_id == account.id,
                PublishingHistory.status == "published")
        .count()
    )
    base_followers = account.followers_count or _deterministic(account.id, today, "base", 5000, 40000)
    new_followers = _deterministic(account.id, today, "nf", 5, 220) if posts else 0
    followers = base_followers + new_followers
    views = posts * _deterministic(account.id, today, "v", 800, 15000)
    likes = int(views * 0.08)
    comments = int(views * 0.008)
    shares = int(views * 0.012)
    er = round((likes + comments + shares) / views, 4) if views else 0.0

    session.add(AccountMetrics(
        account_id=account.id, captured_at=now, followers=followers,
        following=_deterministic(account.id, today, "fg", 100, 900),
        posts_count=posts, views=views, likes=likes, comments=comments,
        shares=shares, engagement_rate=er, source="simulated",
    ))
    upsert_daily_metric(session, account.id, today, followers=followers,
                        new_followers=new_followers, posts=posts, views=views,
                        likes=likes, comments=comments, shares=shares,
                        engagement_rate=er)
    account.followers_count = followers
    session.flush()
    return {"account_id": account.id, "mode": "simulated", "followers": followers,
            "views": views, "posts": posts}


def _refresh_instagram(session: Session, account: DestinationAccount, creds: dict, now, today) -> dict:
    token = creds["access_token"]
    ig_id = creds.get("ig_user_id") or account.external_id
    if not ig_id:
        account.integration_status = "token_error"
        return {"account_id": account.id, "mode": "instagram", "error": "ig_user_id missing"}
    try:
        resp = httpx.get(
            f"https://graph.facebook.com/v21.0/{ig_id}",
            params={"fields": "followers_count,media_count,follows_count,profile_picture_url",
                    "access_token": token},
            timeout=30.0,
        )
        body = resp.json()
        if resp.status_code >= 400:
            account.integration_status = "token_error"
            return {"account_id": account.id, "mode": "instagram",
                    "error": str(body.get("error", {}).get("message", "api error"))[:300]}
        followers = int(body.get("followers_count") or 0)
        session.add(AccountMetrics(
            account_id=account.id, captured_at=now, followers=followers,
            following=int(body.get("follows_count") or 0),
            posts_count=int(body.get("media_count") or 0), source="api",
        ))
        prev = (
            session.query(AccountMetrics)
            .filter(AccountMetrics.account_id == account.id,
                    AccountMetrics.captured_at < now - timedelta(hours=12))
            .order_by(AccountMetrics.captured_at.desc())
            .first()
        )
        new_followers = followers - (prev.followers if prev else followers)
        account.followers_count = followers
        if body.get("profile_picture_url"):
            account.profile_pic_url = body["profile_picture_url"]
        upsert_daily_metric(session, account.id, today, followers=followers,
                            new_followers=max(0, new_followers))
        session.flush()
        return {"account_id": account.id, "mode": "instagram", "followers": followers}
    except httpx.HTTPError as e:
        return {"account_id": account.id, "mode": "instagram", "error": str(e)[:300]}


def _refresh_youtube(session: Session, account: DestinationAccount, creds: dict, now, today) -> dict:
    from memes_shared.services.publishers.youtube import _refresh

    token = creds.get("access_token") or ""
    if not token:
        token, err = _refresh(creds)
        if err:
            account.integration_status = "token_error"
            return {"account_id": account.id, "mode": "youtube", "error": err}
    try:
        resp = httpx.get(
            f"{API_BASE}/channels",
            params={"part": "statistics", "mine": "true",
                    "access_token": token},
            timeout=30.0,
        )
        body = resp.json()
        items = body.get("items") or []
        if not items:
            account.integration_status = "token_error"
            return {"account_id": account.id, "mode": "youtube", "error": "channel not reachable"}
        st = items[0].get("statistics", {})
        followers = int(st.get("subscriberCount") or 0)
        views = int(st.get("viewCount") or 0)
        posts = int(st.get("videoCount") or 0)
        session.add(AccountMetrics(
            account_id=account.id, captured_at=now, followers=followers,
            posts_count=posts, views=views, source="api",
        ))
        prev = (
            session.query(AccountMetrics)
            .filter(AccountMetrics.account_id == account.id,
                    AccountMetrics.captured_at < now - timedelta(hours=12))
            .order_by(AccountMetrics.captured_at.desc())
            .first()
        )
        account.followers_count = followers
        upsert_daily_metric(session, account.id, today, followers=followers,
                            new_followers=max(0, followers - (prev.followers if prev else followers)),
                            posts=posts, views=views)
        session.flush()
        return {"account_id": account.id, "mode": "youtube", "followers": followers}
    except httpx.HTTPError as e:
        return {"account_id": account.id, "mode": "youtube", "error": str(e)[:300]}


API_BASE = "https://www.googleapis.com/youtube/v3"


def refresh_all(session: Session) -> list[dict]:
    out = []
    for account in session.query(DestinationAccount).filter(
        DestinationAccount.status == "active"
    ).all():
        try:
            out.append(refresh_account_metrics(session, account))
        except Exception as e:
            log.exception("metrics refresh failed for account %s", account.id)
            out.append({"account_id": account.id, "error": str(e)[:200]})
    return out
