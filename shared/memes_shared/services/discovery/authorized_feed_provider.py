"""Authorized feed provider — discovery from sources explicitly marked
'authorized' for content reuse (partners' RSS/JSON feeds)."""
from __future__ import annotations

import json

import httpx

from memes_shared.models import ContentSource, RssFeed
from memes_shared.services.discovery.base import (
    DiscoveryItem,
    DiscoveryProvider,
    DiscoveryUnavailable,
)
from memes_shared.utils.timeutil import parse_iso


def _coerce_item(raw: dict, default_category: str) -> DiscoveryItem:
    published = parse_iso(
        str(raw.get("published_at") or raw.get("published") or raw.get("date") or "")
    )
    return DiscoveryItem(
        external_id=str(raw.get("id") or raw.get("external_id") or raw.get("url") or ""),
        title=str(raw.get("title") or ""),
        url=str(raw.get("url") or raw.get("link") or ""),
        media_url=str(raw.get("media_url") or raw.get("video_url") or ""),
        media_type=str(raw.get("media_type") or "video"),
        thumbnail_url=str(raw.get("thumbnail_url") or ""),
        description=str(raw.get("description") or raw.get("summary") or ""),
        author=str(raw.get("author") or ""),
        category=str(raw.get("category") or default_category),
        published_at=published,
        raw_metrics=dict(raw.get("metrics") or {}),
    )


class AuthorizedFeedProvider(DiscoveryProvider):
    """Fetches a JSON list of items from an authorized partner endpoint.

    Expected payload: a JSON array of item objects, or {"items": [...]}.
    """

    name = "authorized_feed"

    def supports(self, source_type: str) -> bool:
        return source_type == "authorized_feed"

    def fetch(self, source: ContentSource, feed: RssFeed | None = None):
        url = source.url
        if not url:
            raise DiscoveryUnavailable("authorized feed source has no URL")
        try:
            resp = httpx.get(url, timeout=30.0, follow_redirects=True,
                             headers={"User-Agent": "MemesPagesAgent/1.0"})
        except httpx.HTTPError as e:
            raise DiscoveryUnavailable(f"authorized feed fetch failed: {e}") from e
        if resp.status_code >= 400:
            raise DiscoveryUnavailable(f"authorized feed HTTP {resp.status_code}")
        try:
            data = resp.json()
        except json.JSONDecodeError as e:
            raise DiscoveryUnavailable("authorized feed returned non-JSON payload") from e
        raw_items = data if isinstance(data, list) else (data.get("items") or [])
        category = source.categories[0] if source.categories else "memes"
        items = [_coerce_item(r, category) for r in raw_items if isinstance(r, dict)]
        return items, {}
