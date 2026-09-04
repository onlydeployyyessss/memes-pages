"""Publisher registry — official APIs + dry-run. Nothing else."""
from __future__ import annotations

from memes_shared.services.publishers.base import PublishResult, Publisher
from memes_shared.services.publishers.dry_run import DryRunPublisher
from memes_shared.services.publishers.instagram import InstagramPublisher
from memes_shared.services.publishers.youtube import YouTubePublisher

REGISTRY: dict[str, Publisher] = {
    "instagram": InstagramPublisher(),
    "youtube": YouTubePublisher(),
    "dry_run": DryRunPublisher(),
    # tiktok has no generally-available direct-post API for unverified apps:
    # accounts on this platform run through dry-run until connected properly.
    "tiktok": DryRunPublisher(),
    "custom": DryRunPublisher(),
}


def get_publisher(platform: str) -> Publisher:
    return REGISTRY.get(platform) or REGISTRY["dry_run"]


__all__ = ["Publisher", "PublishResult", "get_publisher", "REGISTRY"]
