"""Dry-run publisher — simulates publishing end-to-end (default mode)."""
from __future__ import annotations

import hashlib
import time

from memes_shared.logging_setup import get_logger
from memes_shared.models import DestinationAccount, PublishingJob
from memes_shared.services.publishers.base import PublishResult, Publisher

log = get_logger("memes.publishers.dryrun")


class DryRunPublisher(Publisher):
    name = "dry_run"

    def publish(self, *, video_path: str, caption: str, cover_path: str,
                account: DestinationAccount, job: PublishingJob, creds: dict) -> PublishResult:
        # validate the file actually exists — keeps the pipeline honest
        from pathlib import Path

        p = Path(video_path)
        if not p.exists():
            return PublishResult(success=False, error=f"video file missing: {video_path}",
                                 error_type="invalid")
        digest = hashlib.sha256(f"{account.id}:{job.id}:{p.name}".encode()).hexdigest()[:16]
        log.info("[DRY-RUN] would publish '%s' to @%s (job #%s, %.1f MB)",
                 p.name, account.username or account.name, job.id, p.stat().st_size / 1e6)
        return PublishResult(
            success=True,
            external_id=f"dryrun_{digest}",
            permalink=f"https://example.com/@{account.username}/reel/{digest}",
            raw={"mode": "dry_run", "job_id": job.id, "caption_length": len(caption or "")},
        )
