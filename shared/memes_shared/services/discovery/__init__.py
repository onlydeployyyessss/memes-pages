"""Discovery registry + orchestration (used by Trend Hunter)."""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy.orm import Session

from memes_shared.logging_setup import get_logger
from memes_shared.models import AutomationLog, ContentSource, DiscoveredContent, RssFeed
from memes_shared.services.discovery.agent_reach_provider import AgentReachProvider
from memes_shared.services.discovery.authorized_feed_provider import AuthorizedFeedProvider
from memes_shared.services.discovery.base import (
    DiscoveryError,
    DiscoveryItem,
    DiscoveryProvider,
    DiscoveryUnavailable,
)
from memes_shared.services.discovery.rss_provider import RSSProvider
from memes_shared.utils.timeutil import utcnow

log = get_logger("memes.discovery")

PROVIDERS: list[DiscoveryProvider] = [
    RSSProvider(),
    AuthorizedFeedProvider(),
    AgentReachProvider(),
]


def get_provider(source: ContentSource) -> DiscoveryProvider | None:
    for p in PROVIDERS:
        if p.supports(source.source_type):
            return p
    return None


def discover_source(session: Session, source: ContentSource) -> tuple[int, int]:
    """Fetch items for one source and upsert DiscoveredContent rows.

    Returns (created, skipped). Never raises for provider errors — errors are
    recorded on the source counters and an AutomationLog row.
    """
    provider = get_provider(source)
    run_id = f"disc_{utcnow().strftime('%Y%m%d%H%M%S')}_{source.id}"
    started = utcnow()
    if provider is None:
        return _log_and_return(session, run_id, source, "failed", 0, 0,
                               f"no provider supports source type '{source.source_type}'")
    try:
        feed = source.rss_feed
        items, meta = provider.fetch(source, feed)
    except DiscoveryError as e:
        source.error_count = (source.error_count or 0) + 1
        session.add(ErrorLogRow(scope="discovery", error_type=type(e).__name__, message=str(e),
                                context={"source_id": source.id}))
        return _log_and_return(session, run_id, source, "failed", 0, 0, str(e))

    now = utcnow()
    max_age = 24 * 30  # hard safety: nothing older than 30 days is stored
    created = skipped = 0
    for item in items:
        if not item.url and not item.media_url:
            skipped += 1
            continue
        exists = (
            session.query(DiscoveredContent)
            .filter(
                (DiscoveredContent.external_id == item.external_id)
                if item.external_id
                else (DiscoveredContent.url == item.url)
            )
            .first()
        )
        if exists is not None:
            skipped += 1
            continue
        if item.published_at and (now - item.published_at) > timedelta(hours=max_age):
            skipped += 1
            continue
        session.add(
            DiscoveredContent(
                source_id=source.id,
                rss_feed_id=feed.id if feed else None,
                external_id=item.external_id[:255],
                title=item.title[:2000],
                url=item.url,
                media_url=item.media_url,
                media_type=item.media_type,
                thumbnail_url=item.thumbnail_url,
                description=item.description[:4000],
                author=item.author[:160],
                category=item.category or "memes",
                published_at=item.published_at,
                discovered_at=now,
                raw_metrics=dict(item.raw_metrics),
                status="detected",
            )
        )
        created += 1

    source.last_checked_at = now
    source.success_count = (source.success_count or 0) + 1
    if meta.get("etag") and feed is not None:
        feed.etag = meta["etag"][:255]
    if meta.get("last_modified") and feed is not None:
        feed.last_modified = meta["last_modified"][:255]
    if feed is not None:
        feed.last_checked_at = now
        feed.items_seen = (feed.items_seen or 0) + len(items)
    return _log_and_return(session, run_id, source, "success", created, skipped,
                           f"{created} new / {skipped} skipped of {len(items)} items",
                           started=started)


def _log_and_return(
    session: Session,
    run_id: str,
    source: ContentSource,
    status: str,
    created: int,
    skipped: int,
    message: str,
    started: "utcnow | None" = None,
):
    from memes_shared.utils.timeutil import utcnow as _u

    started = started or _u()
    duration_ms = int((_u() - started).total_seconds() * 1000)
    session.add(
        AutomationLog(
            run_id=run_id,
            job_name=f"discovery:{source.source_type}",
            status=status,
            message=f"[{source.name}] {message}",
            items_processed=created,
            duration_ms=duration_ms,
            started_at=started,
            finished_at=_u(),
            meta={"source_id": source.id, "skipped": skipped},
        )
    )
    session.flush()
    log.info("discovery[%s] %s: +%d/-%d %s", source.source_type, source.name, created, skipped, message)
    return created, skipped


def ErrorLogRow(**kwargs):
    from memes_shared.models import ErrorLog

    return ErrorLog(**kwargs)


def run_discovery_cycle(session: Session) -> dict:
    """Run every enabled, due source. Returns summary."""
    now = utcnow()
    sources = session.query(ContentSource).filter(ContentSource.enabled.is_(True)).all()
    total_created = 0
    results = []
    for src in sources:
        due = (
            src.last_checked_at is None
            or (now - src.last_checked_at).total_seconds() / 60.0
            >= max(1, src.check_interval_minutes or 15)
        )
        if not due:
            continue
        created, _ = discover_source(session, src)
        total_created += created
        results.append({"source": src.name, "created": created})
    return {"checked": len(sources), "created": total_created, "results": results}


__all__ = [
    "DiscoveryItem",
    "DiscoveryProvider",
    "DiscoveryError",
    "DiscoveryUnavailable",
    "RSSProvider",
    "AuthorizedFeedProvider",
    "AgentReachProvider",
    "PROVIDERS",
    "get_provider",
    "discover_source",
    "run_discovery_cycle",
]
