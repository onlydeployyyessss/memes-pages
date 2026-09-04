"""RSS / Atom feed provider (primary, fully supported)."""
from __future__ import annotations

from datetime import datetime, timezone

import feedparser
import httpx

from memes_shared.logging_setup import get_logger
from memes_shared.models import ContentSource, RssFeed
from memes_shared.services.discovery.base import (
    DiscoveryItem,
    DiscoveryProvider,
    DiscoveryUnavailable,
)
from memes_shared.utils.timeutil import parse_iso

log = get_logger("memes.discovery.rss")

USER_AGENT = "MemesPagesAgent/1.0 (+https://github.com/memes-pages)"


def _entry_media(entry: dict) -> tuple[str, str]:
    """Extract (media_url, media_type) from enclosures / media:content / links."""
    for enc in entry.get("enclosures", []) or []:
        href = enc.get("href") or ""
        ctype = (enc.get("type") or "").lower()
        if href and (ctype.startswith("video") or "video" in href or Path_is_video(href)):
            return href, "video"
    media_content = entry.get("media_content") or []
    for m in media_content:
        url = m.get("url") or ""
        mtype = (m.get("type") or m.get("medium") or "").lower()
        if url and ("video" in mtype or Path_is_video(url)):
            return url, "video"
    for m in media_content:
        url = m.get("url") or ""
        mtype = (m.get("type") or m.get("medium") or "").lower()
        if url and ("image" in mtype or "image" in m.get("type", "")):
            return url, "image"
    # Some feeds put the video link as the plain link
    link = entry.get("link") or ""
    if link and Path_is_video(link):
        return link, "video"
    return "", ""


def Path_is_video(url: str) -> bool:
    return url.lower().split("?")[0].endswith(
        (".mp4", ".mov", ".webm", ".mkv", ".m4v", ".avi")
    )


def _entry_metrics(entry: dict) -> dict:
    """Best-effort metric extraction from common RSS extensions."""
    metrics: dict = {}
    for key in ("views", "likes", "comments", "shares"):
        for cand in (f"{key}", f"media_{key}", f"{key}_count"):
            v = entry.get(cand)
            if v is not None:
                try:
                    metrics[key] = int(float(str(v).replace(",", "")))
                    break
                except (TypeError, ValueError):
                    pass
    # media:starRating (mediaRSS)
    rating = (entry.get("media_statistics") or {}).get("views") or entry.get("stars")
    if rating is not None and "views" not in metrics:
        try:
            metrics["views"] = int(float(str(rating).replace(",", "")))
        except (TypeError, ValueError):
            pass
    return metrics


class RSSProvider(DiscoveryProvider):
    name = "rss"

    def supports(self, source_type: str) -> bool:
        return source_type in ("rss", "authorized_feed", "webhook")

    def fetch(self, source: ContentSource, feed: RssFeed | None = None):
        url = (feed.url if feed else None) or source.url
        if not url:
            raise DiscoveryUnavailable("RSS source has no URL configured")
        headers = {"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/xml, text/xml, */*"}
        if feed is not None and feed.etag:
            headers["If-None-Match"] = feed.etag
        if feed is not None and feed.last_modified:
            headers["If-Modified-Since"] = feed.last_modified
        try:
            resp = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
        except httpx.HTTPError as e:
            raise DiscoveryUnavailable(f"RSS fetch failed: {e}") from e
        if resp.status_code == 304:
            return [], {"not_modified": True}
        if resp.status_code >= 400:
            raise DiscoveryUnavailable(f"RSS fetch HTTP {resp.status_code} for {url}")

        parsed = feedparser.parse(resp.content)
        if parsed.bozo and not parsed.entries:
            raise DiscoveryUnavailable(f"RSS parse error: {getattr(parsed, 'bozo_exception', 'unknown')}")

        items: list[DiscoveryItem] = []
        for e in parsed.entries:
            media_url, media_type = _entry_media(e)
            published = None
            for key in ("published_parsed", "updated_parsed"):
                st = e.get(key)
                if st:
                    try:
                        published = datetime(*st[:6], tzinfo=timezone.utc)
                        break
                    except (TypeError, ValueError):
                        pass
            if published is None:
                published = parse_iso(e.get("published") or e.get("updated"))
            items.append(
                DiscoveryItem(
                    external_id=e.get("id") or e.get("guid") or e.get("link", ""),
                    title=(e.get("title") or "").strip(),
                    url=e.get("link") or "",
                    media_url=media_url,
                    media_type=media_type or "video",
                    thumbnail_url=(
                        ((e.get("media_thumbnail") or [{}])[0].get("url")) if e.get("media_thumbnail") else ""
                    ),
                    description=e.get("summary") or e.get("description") or "",
                    author=(e.get("author") or ""),
                    category=(feed.category if feed else source.categories[0] if source.categories else "memes"),
                    published_at=published,
                    raw_metrics=_entry_metrics(e),
                )
            )
        meta = {
            "etag": resp.headers.get("etag", ""),
            "last_modified": resp.headers.get("last-modified", ""),
        }
        return items, meta
