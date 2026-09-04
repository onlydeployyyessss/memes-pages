"""InstaLoader integration — bulk-import reels from Instagram profiles.

Ethics/safety contract (operator responsibility):
  Only import content you own or have permission to re-post. Instagram
  rate-limits datacenter IPs aggressively, so:
    - downloads are paced (sleep between fetches) and capped per job
    - an optional IG login (session file, encrypted-at-rest path) raises
      limits; use a BURNER account — never the posting account's login.
  The pipeline itself stays unchanged: imported videos go through the same
  trend-score -> FFmpeg -> queue -> schedule flow as manual uploads.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread

import httpx
from fastapi import APIRouter, Depends, HTTPException
from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger
from memes_shared.models import DiscoveredContent
from pydantic import BaseModel, Field

from backend.app.deps import current_admin

log = get_logger("memes.instaloader")

router = APIRouter(dependencies=[Depends(current_admin)])

# in-memory job status (survives until api restart; results persist in the content table)
JOB: dict = {"running": False, "profile": "", "fetched": 0, "queued": 0, "failed": 0,
             "messages": [], "started_at": "", "finished_at": ""}
_CANCEL = False
JOB_DEADLINE_S = 900  # hard stop: 15 minutes per job

MAX_PER_JOB = 30          # hard cap per fetch job
SLEEP_BETWEEN_S = 8.0     # pacing between downloads
SESSION_SUBDIR = "instaloader"


def _session_dir() -> Path:
    d = get_settings().media_path / SESSION_SUBDIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _session_path(username: str) -> Path:
    return _session_dir() / f"session-{username}.session"


def _lazy_instaloader():
    try:
        import instaloader
        return instaloader
    except ImportError as e:  # pragma: no cover - guarded by requirements
        raise HTTPException(503, "instaloader is not installed on the server") from e


def _make_loader(instaloader):
    """Metadata-only loader (we stream videos ourselves with httpx)."""
    return instaloader.Instaloader(
        download_pictures=False, download_videos=False, download_video_thumbnails=False,
        download_comments=False, save_metadata=False, compress_json=False,
        post_metadata_txt_pattern="", filename_pattern="{shortcode}",
        quiet=True, user_agent="Mozilla/5.0 (compatible; MemesPagesAgent/1.0)",
    )


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class FetchIn(BaseModel):
    profile: str = Field(min_length=1, max_length=60)
    limit: int = Field(default=10, ge=1, le=MAX_PER_JOB)
    sleep_seconds: float = Field(default=SLEEP_BETWEEN_S, ge=2.0, le=30.0)


@router.post("/login")
def instaloader_login(body: LoginIn):
    """Create a session file for a (burner) IG login. Password is used once, never stored."""
    instaloader = _lazy_instaloader()
    L = _make_loader(instaloader)
    try:
        L.login(body.username, body.password)
        L.save_session_to_file(str(_session_path(body.username)))
    except Exception as e:
        msg = str(e)
        if "2FA" in msg or "two-factor" in msg.lower():
            raise HTTPException(400, "2FA is enabled on this account — use an app password or disable 2FA for the importer login") from None
        raise HTTPException(400, f"Instagram login failed: {msg[:200]}") from None
    return {"ok": True, "username": body.username,
            "message": "session saved (password not stored). Use a burner account for imports."}


@router.get("/status")
def instaloader_status():
    sessions = sorted(p.name for p in _session_dir().glob("session-*.session"))
    return {"job": JOB, "sessions": [s.replace("session-", "").replace(".session", "") for s in sessions]}


@router.delete("/session/{username}")
def instaloader_logout(username: str):
    p = _session_path(username)
    existed = p.exists()
    p.unlink(missing_ok=True)
    return {"ok": True, "removed": existed}


def _collect_video_posts(instaloader, profile: str, limit: int) -> list[dict]:
    """Newest-first video posts (metadata only — no media downloaded here)."""
    L = _make_loader(instaloader)
    L.context.max_connection_attempts = 2  # fail fast instead of hanging on 429 backoff
    sessions = sorted(_session_dir().glob("session-*.session"))
    if sessions:
        try:
            L.load_session_from_file(sessions[-1].name.replace("session-", "").replace(".session", ""),
                                     str(sessions[-1]))
            log.info("instaloader: using session %s", sessions[-1].name)
        except Exception as e:
            log.warning("instaloader: session load failed (%s) — going anonymous", e)
    try:
        profile_obj = instaloader.Profile.from_username(L.context, profile)
        out: list[dict] = []
        for post in profile_obj.get_posts():
            if not post.is_video:
                continue
            out.append({
                "shortcode": post.shortcode,
                "video_url": post.video_download_url,
                "caption": (post.caption or "")[:200],
                "date": post.date_utc.isoformat() if post.date_utc else "",
                "title": f"@{profile} reel {post.shortcode}",
            })
            if len(out) >= limit:
                break
        return out
    except instaloader.exceptions.TooManyRequestsException:
        raise HTTPException(429, "Instagram rate limit hit (429) — wait ~15 minutes, reduce the batch size, or import from the phone app instead") from None
    except instaloader.exceptions.ProfileNotExistsException:
        raise HTTPException(404, f"Instagram profile '{profile}' does not exist (or is private without a session)") from None
    except instaloader.exceptions.ConnectionException as e:
        raise HTTPException(502, f"Instagram connection problem: {str(e)[:150]} — try again later or use a session login") from None


def _stream_to_uploads(video_url: str) -> Path:
    cfg = get_settings()
    uploads = cfg.media_path / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    dest = uploads / f"instaload_{uuid.uuid4().hex[:12]}.mp4"
    size = 0
    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        with client.stream("GET", video_url) as r:
            if r.status_code >= 400:
                raise RuntimeError(f"video download HTTP {r.status_code}")
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(1 << 20):
                    size += len(chunk)
                    if size > 500 * 1024 * 1024:
                        f.close()
                        dest.unlink(missing_ok=True)
                        raise RuntimeError("video exceeds 500 MB")
                    f.write(chunk)
    return dest


def _run_job(profile: str, limit: int, sleep_s: float):
    global JOB
    from memes_shared.db.session import SessionLocal

    instaloader = _lazy_instaloader()
    deadline = time.time() + JOB_DEADLINE_S
    try:
        posts = _collect_video_posts(instaloader, profile, limit)
    except HTTPException as e:
        JOB.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())
        JOB["messages"].append(f"🔴 {e.detail}")
        return
    if _CANCEL:
        JOB.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())
        JOB["messages"].append("🛑 cancelled before download phase")
        return

    from backend.app.routers.content import _process_local_video

    for i, p in enumerate(posts):
        if _CANCEL or time.time() > deadline:
            JOB["messages"].append("🛑 stopped (cancel or 15-min cap)")
            break
        if JOB["fetched"] + JOB["failed"] >= limit:
            break
        try:
            dest = _stream_to_uploads(p["video_url"])
            with SessionLocal() as db:
                content = DiscoveredContent(
                    source_id=None,
                    external_id=f"ig_{p['shortcode']}",
                    title=p["title"],
                    url=f"https://www.instagram.com/reel/{p['shortcode']}/",
                    media_url="", media_type="video",
                    category="memes",
                    description=p["caption"],
                    discovered_at=datetime.now(timezone.utc),
                    raw_metrics={"instaloader": True, "profile": profile, "shortcode": p["shortcode"]},
                    status="detected",
                )
                db.add(content)
                db.flush()
                if db.query(DiscoveredContent).filter(
                        DiscoveredContent.external_id == f"ig_{p['shortcode']}",
                        DiscoveredContent.id != content.id).count():
                    db.rollback()
                    JOB["messages"].append(f"↩️ {p['shortcode']}: already imported (dedup)")
                    dest.unlink(missing_ok=True)
                    continue
                from memes_shared.models import TrendScore
                from memes_shared.services.trend_engine import compute_trend_score

                score, breakdown = compute_trend_score(
                    {"views": 0, "likes": 0, "comments": 0, "shares": 0}, None,
                    trend_cfg=None, history=None)
                db.add(TrendScore(content_id=content.id, score=score, signals=breakdown))
                video, error = _process_local_video(db, content, str(dest))
                if video is None:
                    content.status = "failed"
                    content.error = error or "processing failed"
                    JOB["failed"] += 1
                    JOB["messages"].append(f"🔴 {p['shortcode']}: {error}")
                else:
                    from memes_shared.services.publishing import create_jobs_for_content

                    jobs = create_jobs_for_content(db, content, video)
                    content.status = "queued" if jobs else "skipped"
                    if not jobs:
                        content.error = "no eligible destination accounts"
                    JOB["queued"] += 1 if jobs else 0
                    JOB["fetched"] += 1
                    JOB["messages"].append(
                        f"{'🟢' if jobs else '⚪'} {p['shortcode']}: {content.status}")
                db.commit()
        except Exception as e:
            JOB["failed"] += 1
            JOB["messages"].append(f"🔴 {p.get('shortcode', '?')}: {str(e)[:120]}")
            log.warning("instaloader import error: %s", e)
        if i < len(posts) - 1:
            time.sleep(sleep_s)

    JOB["running"] = False
    JOB["finished_at"] = datetime.now(timezone.utc).isoformat()
    JOB["messages"].append(f"✅ job done — fetched {JOB['fetched']}, queued {JOB['queued']}, failed {JOB['failed']}")


@router.post("/cancel")
def instaloader_cancel():
    """Signal the running job to stop at the next checkpoint."""
    global _CANCEL
    if not JOB.get("running"):
        return {"ok": True, "note": "no job running"}
    _CANCEL = True
    JOB["messages"].append("🛑 cancel requested — stopping at next checkpoint")
    return {"ok": True, "note": "cancel signalled; the job stops at the next checkpoint (a 429-stuck fetch phase exits within ~2 min)"}


@router.post("/fetch")
def instaloader_fetch(body: FetchIn):
    global JOB, _CANCEL
    if JOB["running"]:
        raise HTTPException(409, "an import job is already running — check status or cancel it")
    _CANCEL = False
    profile = body.profile.strip().lstrip("@").split("/")[0]
    JOB = {"running": True, "profile": profile, "fetched": 0, "queued": 0, "failed": 0,
           "messages": [f"📥 importing up to {body.limit} reels from @{profile}…"],
           "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": ""}
    Thread(target=_run_job, args=(profile, body.limit, body.sleep_seconds), daemon=True).start()
    return {"ok": True, "job": JOB,
            "note": "running in background — poll GET /instaloader/status or watch the Content page"}
