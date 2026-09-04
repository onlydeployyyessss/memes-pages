"""Content pipeline: validate → dedup → download → process → queue.

New Content → Validate Source → Validate Media → Duplicate Detection →
Download → Store Temp → Video Validation → Media Hash → Metadata →
Content Queue → (multi-account publishing jobs)
"""
from __future__ import annotations

import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger
from memes_shared.models import (
    AutomationLog,
    ContentSource,
    DiscoveredContent,
    Video,
    VideoHash,
)
from memes_shared.services import dedup, media as media_svc, video as video_svc
from memes_shared.services.settings import get_setting
from memes_shared.utils.timeutil import utcnow

log = get_logger("memes.pipeline")


def _log_run(session: Session, job_name: str, status: str, message: str,
             items: int = 0, duration_ms: int = 0, run_id: str = "") -> None:
    session.add(
        AutomationLog(
            run_id=run_id or f"pipe_{utcnow().strftime('%Y%m%d%H%M%S%f')}",
            job_name=job_name,
            status=status,
            message=message[:1900],
            items_processed=items,
            duration_ms=duration_ms,
            started_at=utcnow(),
            finished_at=utcnow(),
        )
    )


def process_content(session: Session, content: DiscoveredContent) -> str:
    """Run the full pipeline for one discovered item. Returns final status."""
    started = utcnow()
    settings_media = get_settings().media_path
    tmp_dir = settings_media / "tmp"
    store_dir = settings_media / "videos"
    cover_dir = settings_media / "covers"
    try:
        # ── 1. Validate source ────────────────────────────────────────
        source = session.get(ContentSource, content.source_id) if content.source_id else None
        if source is not None:
            if not source.enabled:
                content.status = "skipped"
                content.error = "source is disabled"
                return content.status
            if source.authorization != "authorized":
                content.status = "skipped"
                content.error = f"source not authorized ({source.authorization})"
                return content.status

        # ── 2. Media availability ─────────────────────────────────────
        if not content.media_url:
            content.status = "skipped"
            content.error = "no downloadable media URL"
            return content.status

        # ── 3. Pre-download duplicate detection (url / external id) ───
        pre = dedup.check_pre_download(session, source_url=content.url, external_id=content.external_id)
        if pre.is_duplicate:
            content.status = "skipped"
            content.error = f"duplicate: {pre.reason_text}"
            return content.status

        content.status = "processing"
        session.flush()

        # ── 4. Download (authorized media only) ───────────────────────
        original = media_svc.download(content.media_url, tmp_dir)

        # ── 5. Video validation ───────────────────────────────────────
        info, err = video_svc.validate_video(original)
        if err:
            original.unlink(missing_ok=True)
            content.status = "failed"
            content.error = f"video validation failed: {err}"
            _log_run(session, "pipeline", "failed", f"#{content.id} {content.error}")
            return content.status

        # ── 6. Hashes + media-level duplicate detection ───────────────
        sha = dedup.sha256_file(original)
        frame_hashes: list[str] = []
        try:
            frame_hashes = dedup.extract_frame_hashes(original)
        except Exception as e:  # noqa: BLE001 — dedup must not block pipeline
            log.warning("phash extraction failed for #%s: %s", content.id, e)
        dup = dedup.check_media(session, sha256=sha, phash_frames=frame_hashes)
        if dup.is_duplicate:
            original.unlink(missing_ok=True)
            content.status = "skipped"
            content.error = f"duplicate: {dup.reason_text}"
            _log_run(session, "pipeline", "success", f"#{content.id} skipped as duplicate ({dup.reason_text})")
            return content.status

        # ── 7. Normalize + cover ──────────────────────────────────────
        normalized = video_svc.normalize_video(original, tmp_dir)
        cover_path = ""
        try:
            cover_path = str(video_svc.extract_cover(normalized, cover_dir))
        except Exception as e:  # noqa: BLE001
            log.warning("cover extraction failed for #%s: %s", content.id, e)

        # ── 8. Persist video + hashes + metadata ──────────────────────
        final_path = store_dir / normalized.name
        normalized.replace(final_path)
        original.unlink(missing_ok=True)

        video = Video(
            content_id=content.id,
            file_path=str(final_path),
            original_path=content.media_url[:2000],
            cover_path=cover_path,
            file_size=final_path.stat().st_size,
            duration=info.get("duration", 0.0),
            width=info.get("width", 0),
            height=info.get("height", 0),
            fps=info.get("fps", 0.0),
            has_audio=info.get("has_audio", True),
            status="ready",
        )
        session.add(video)
        session.flush()
        session.add(
            VideoHash(
                video_id=video.id,
                sha256=sha,
                phash=":".join(frame_hashes),
                phash_frames=len(frame_hashes),
                source_url_hash=dedup.sha256_file(final_path)[:64] if not content.url else __import__("hashlib").sha256(content.url.encode()).hexdigest(),
            )
        )
        content.processed_at = utcnow()

        # ── 9. Multi-account distribution → publishing queue ──────────
        from memes_shared.services.publishing import create_jobs_for_content

        jobs = create_jobs_for_content(session, content, video)
        content.status = "queued" if jobs else "skipped"
        if not jobs:
            content.error = "no eligible destination accounts"

        _log_run(
            session, "pipeline", "success",
            f"#{content.id} '{(content.title or '')[:60]}' ready ({info['width']}x{info['height']}, "
            f"{info['duration']:.1f}s) → {len(jobs)} job(s)",
            items=len(jobs),
            duration_ms=int((utcnow() - started).total_seconds() * 1000),
        )
        return content.status

    except (media_svc.MediaDownloadError, video_svc.VideoProcessingError, Exception) as e:
        log.exception("pipeline failed for content #%s", content.id)
        content.status = "failed"
        content.error = str(e)[:1500]
        from memes_shared.models import ErrorLog

        session.add(
            ErrorLog(
                scope="pipeline",
                error_type=type(e).__name__,
                message=str(e)[:1900],
                context={"content_id": content.id, "media_url": content.media_url[:500]},
                severity="error",
            )
        )
        _log_run(session, "pipeline", "failed", f"#{content.id} {type(e).__name__}: {str(e)[:300]}")
        return content.status


def process_pending(session: Session, limit: int = 10) -> dict:
    """Process items flagged 'processing' (retry) or newly approved."""
    rows = (
        session.query(DiscoveredContent)
        .filter(DiscoveredContent.status == "processing")
        .order_by(DiscoveredContent.discovered_at)
        .limit(limit)
        .all()
    )
    done = {}
    for row in rows:
        done[str(row.id)] = process_content(session, row)
    return {"processed": len(rows), "statuses": done}
