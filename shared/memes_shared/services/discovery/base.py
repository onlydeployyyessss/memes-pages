"""Discovery Provider Interface.

Every discovery source (RSS, authorized feeds, Agent-Reach, future
providers) implements this interface. The rest of the system depends only
on the abstraction — never on a specific provider.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from memes_shared.models import ContentSource, RssFeed


@dataclass
class DiscoveryItem:
    external_id: str = ""
    title: str = ""
    url: str = ""
    media_url: str = ""
    media_type: str = "video"
    thumbnail_url: str = ""
    description: str = ""
    author: str = ""
    category: str = "memes"
    published_at: datetime | None = None
    raw_metrics: dict[str, Any] = field(default_factory=dict)


class DiscoveryError(Exception):
    """Provider-level failure (network, parse, availability)."""


class DiscoveryUnavailable(DiscoveryError):
    """Provider binary/service not available — system must continue without it."""


class DiscoveryProvider(ABC):
    """Contract: fetch discovery items for a configured source."""

    name: str = "base"

    @abstractmethod
    def supports(self, source_type: str) -> bool: ...

    @abstractmethod
    def fetch(
        self, source: ContentSource, feed: RssFeed | None = None
    ) -> tuple[list[DiscoveryItem], dict]:
        """Return (items, meta) where meta may carry etag/last_modified/etc.

        Raise DiscoveryError subclasses on failure. Implementations must be
        best-effort: errors are logged and never halt the automation loop.
        """
