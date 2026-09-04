"""InstaLoader service — bulk reel import from Instagram profiles.

Shared by the API (manual imports, /instaloader/*) and the worker
(watchlist auto-imports). Sessions are stored ENCRYPTED in app_settings
(single source of truth for api + worker; survives redeploys; password
is used once and never persisted).

Safety rails: per-job cap, paced downloads, cancel check, deadline,
duplicate guard (ig_<shortcode> external_id). Only import content you
own or have permission to re-post.
"""
from __future__ import annotations

import base64
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import httpx

from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger
from memes_shared.security import decrypt_credential, encrypt_credential
from memes_shared.services.settings import get_setting, set_setting

log = get_logger("memes.instaloader")

MAX_PER_JOB = 30
DEFAULT_SLEEP_S = 8.0
DEFAULT_DEADLINE_S = 900
WATCHLIST_KEY = "instaloader_watchlist"
SESSION_KEY_PREFIX = "instaloader_session_"


# ── Sessions (DB-backed, encrypted) ─────────────────────────────────────


def login_save(username: str, password: str) -> dict:
    instaloader = _lazy()
    L = _base_loader(instaloader)
    try:
        L.login(username, password)
        fd, tmp_path = tempfile.mkstemp(suffix=".session")
        import os

        os.close(fd)
        L.save_session_to_file(tmp_path)
        blob = base64.b64encode(Path(tmp_path).read_bytes()).decode()
        Path(tmp_path).unlink(missing_ok=True)
    except Exception as e:
        msg = str(e)
        if "Checkpoint required" in msg or "checkpoint" in msg.lower():
            raise ValueError(
                "Instagram security checkpoint: log in once as this account in the app/browser and approve the login (\"This was me\"), then retry."
            ) from None
        if "2FA" in msg or "two-factor" in msg.lower():
            raise ValueError("2FA is enabled — use an app password or disable 2FA on the burner account") from None
        if "Incorrect password" in msg or "bad password" in msg.lower():
            raise ValueError("Instagram rejected the credentials (incorrect username/password)") from None
        raise ValueError(f"Instagram login failed: {msg[:180]}") from None
    with get_settings() and _db_session() as db:
        set_setting(db, SESSION_KEY_PREFIX + username, {"blob": encrypt_credential(blob)})
    return {"username": username, "sessions": list_sessions()}


def import_session(username: str, sessionid: str) -> dict:
    """Build a session from a browser sessionid cookie (trusted-login path).

    The user copies the value from their own logged-in browser (F12 →
    Cookies → instagram.com → sessionid). We inject it into instaloader,
    verify it live, and store it encrypted — no password, no checkpoint.
    """
    instaloader = _lazy()
    L = _base_loader(instaloader)
    sess = L.context.get_session() if hasattr(L.context, "get_session") else L.context._session
    sess.cookies.set("sessionid", sessionid.strip(), domain=".instagram.com", path="/")
    L.context.username = username
    who = L.test_login()
    if not who:
        raise ValueError("That sessionid was rejected by Instagram — make sure you copied the FULL value from a logged-in instagram.com tab (F12 → Application → Cookies)")
    fd, tmp_path = tempfile.mkstemp(suffix=".session")
    import os

    os.close(fd)
    L.save_session_to_file(tmp_path)
    blob = base64.b64encode(Path(tmp_path).read_bytes()).decode()
    Path(tmp_path).unlink(missing_ok=True)
    with _db_session() as db:
        set_setting(db, SESSION_KEY_PREFIX + username, {"blob": encrypt_credential(blob)})
    return {"username": username, "logged_in_as": who, "sessions": list_sessions()}


def list_sessions() -> list[str]:
    with _db_session() as db:
        data = get_setting(db, WATCHLIST_KEY)  # ensure settings table touched
        _ = data
        from memes_shared.models import AppSetting

        rows = db.query(AppSetting).filter(AppSetting.key.like(SESSION_KEY_PREFIX + "%")).all()
        return sorted(r.key.replace(SESSION_KEY_PREFIX, "") for r in rows)


def remove_session(username: str) -> bool:
    with _db_session() as db:
        from memes_shared.models import AppSetting

        row = db.get(AppSetting, SESSION_KEY_PREFIX + username)
        if row is None:
            return False
        db.delete(row)
        db.commit()
        return True


def _materialize_sessions() -> list[Path]:
    """Write stored sessions to a temp dir; returns paths newest-first."""
    out: list[Path] = []
    with _db_session() as db:
        from memes_shared.models import AppSetting

        rows = db.query(AppSetting).filter(AppSetting.key.like(SESSION_KEY_PREFIX + "%")).all()
        for r in rows:
            username = r.key.replace(SESSION_KEY_PREFIX, "")
            try:
                blob = base64.b64decode(decrypt_credential(r.value.get("blob", "")))
                p = Path(tempfile.gettempdir()) / f"igsession-{username}.session"
                p.write_bytes(blob)
                out.append(p)
            except Exception as e:
                log.warning("session %s unusable: %s", username, e)
    return out


# ── Post collection + download ───────────────────────────────────────────


def _lazy():
    try:
        import instaloader

        return instaloader
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("instaloader is not installed") from e


def _base_loader(instaloader):
    return instaloader.Instaloader(
        download_pictures=False, download_videos=False, download_video_thumbnails=False,
        download_comments=False, save_metadata=False, compress_json=False,
        post_metadata_txt_pattern="", filename_pattern="{shortcode}",
        quiet=True, user_agent="Mozilla/5.0 (compatible; MemesPagesAgent/1.0)",
    )


def collect_posts(profile: str, limit: int) -> list[dict]:
    instaloader = _lazy()
    L = _base_loader(instaloader)
    L.context.max_connection_attempts = 2  # fail fast instead of 429 backoff loops
    for session_path in _materialize_sessions():
        try:
            L.load_session_from_file(session_path.stem.replace("igsession-", ""), str(session_path))
            log.info("instaloader: using session %s", session_path.name)
            break
        except Exception as e:
            log.warning("instaloader: session %s failed (%s)", session_path.name, e)
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
                "title": f"@{profile} reel {post.shortcode}",
            })
            if len(out) >= limit:
                break
        return out
    except instaloader.exceptions.TooManyRequestsException:
        raise ValueError("Instagram rate limit (429) — wait ~15 minutes, smaller batches, or check the burner session") from None
    except instaloader.exceptions.ProfileNotExistsException:
        raise ValueError(f"Profile '{profile}' does not exist (or is private and the saved session can't see it)") from None
    except instaloader.exceptions.ConnectionException as e:
        raise ValueError(f"Instagram connection problem: {str(e)[:140]}") from None


def download_video(video_url: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"instaload_{uuid.uuid4().hex[:12]}.mp4"
    size = 0
    with httpx.Client(timeout=120.0, follow_redirects=True) as client:
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


# ── Import job (pipeline: download → dedup → score → process → queue) ───


def import_job(
    profile: str,
    limit: int = 10,
    sleep_s: float = DEFAULT_SLEEP_S,
    deadline_s: int = DEFAULT_DEADLINE_S,
    progress: Callable[[dict], None] | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> dict:
    """Import up to `limit` reels from `profile` into the full pipeline.

    Returns {"fetched", "queued", "failed", "messages"}.
    """
    from memes_shared.db.session import SessionLocal
    from memes_shared.models import DiscoveredContent, TrendScore
    from memes_shared.services.pipeline import process_local_video
    from memes_shared.services.publishing import create_jobs_for_content
    from memes_shared.services.trend_engine import compute_trend_score

    stats = {"profile": profile, "fetched": 0, "queued": 0, "failed": 0, "running": True,
             "messages": [f"📥 importing up to {limit} reels from @{profile}…"],
             "started_at": datetime.now(timezone.utc).isoformat(), "finished_at": ""}
    if progress:
        progress(dict(stats))
    deadline = time.time() + deadline_s
    tmp_dir = get_settings().media_path / "tmp"

    try:
        posts = collect_posts(profile, limit)
    except ValueError as e:
        stats.update(running=False, finished_at=datetime.now(timezone.utc).isoformat())
        stats["messages"].append(f"🔴 {e}")
        if progress:
            progress(dict(stats))
        return stats

    for i, p in enumerate(posts):
        if cancel_check and cancel_check():
            stats["messages"].append("🛑 cancelled")
            break
        if time.time() > deadline:
            stats["messages"].append("🛑 stopped at the 15-minute cap")
            break
        if stats["fetched"] + stats["failed"] >= limit:
            break
        ext_id = f"ig_{p['shortcode']}"
        try:
            with SessionLocal() as db:
                if db.query(DiscoveredContent).filter(DiscoveredContent.external_id == ext_id).count():
                    stats["messages"].append(f"↩️ {p['shortcode']}: already imported")
                    if progress:
                        progress(dict(stats))
                    continue
                content = DiscoveredContent(
                    source_id=None, external_id=ext_id, title=p["title"],
                    url=f"https://www.instagram.com/reel/{p['shortcode']}/",
                    media_url="", media_type="video", category="memes",
                    description=p["caption"], discovered_at=datetime.now(timezone.utc),
                    raw_metrics={"instaloader": True, "profile": profile, "shortcode": p["shortcode"]},
                    status="detected",
                )
                db.add(content)
                db.flush()
                src = download_video(p["video_url"], tmp_dir)
                score, breakdown = compute_trend_score(
                    {"views": 0, "likes": 0, "comments": 0, "shares": 0}, None,
                    trend_cfg=None, history=None)
                db.add(TrendScore(content_id=content.id, score=score, signals=breakdown))
                video, error = process_local_video(db, content, str(src))
                if video is None:
                    content.status = "failed"
                    content.error = error or "processing failed"
                    stats["failed"] += 1
                    stats["messages"].append(f"🔴 {p['shortcode']}: {error}")
                else:
                    jobs = create_jobs_for_content(db, content, video)
                    content.status = "queued" if jobs else "skipped"
                    if not jobs:
                        content.error = "no eligible destination accounts"
                    stats["queued"] += 1 if jobs else 0
                    stats["fetched"] += 1
                    stats["messages"].append(f"{'🟢' if jobs else '⚪'} {p['shortcode']}: {content.status}")
                db.commit()
        except Exception as e:
            stats["failed"] += 1
            stats["messages"].append(f"🔴 {p.get('shortcode', '?')}: {str(e)[:120]}")
            log.warning("instaloader import error: %s", e)
        if progress:
            progress(dict(stats))
        if i < len(posts) - 1:
            time.sleep(sleep_s)

    stats["running"] = False
    stats["finished_at"] = datetime.now(timezone.utc).isoformat()
    stats["messages"].append(
        f"✅ done — fetched {stats['fetched']}, queued {stats['queued']}, failed {stats['failed']}")
    if progress:
        progress(dict(stats))
    return stats


# ── Watchlist (scheduled auto-import) ────────────────────────────────────


def get_watchlist() -> list[dict]:
    with _db_session() as db:
        data = get_setting(db, WATCHLIST_KEY)
    return data.get("entries", [])


def watchlist_add(profile: str, limit: int = 10, interval_hours: int = 12) -> list[dict]:
    profile = profile.strip().lstrip("@").split("/")[0]
    with _db_session() as db:
        data = get_setting(db, WATCHLIST_KEY)
        entries = data.get("entries", [])
        for e in entries:
            if e["profile"] == profile:
                e.update(limit=limit, interval_hours=interval_hours, enabled=True)
                break
        else:
            entries.append({"profile": profile, "enabled": True, "limit": limit,
                            "interval_hours": interval_hours, "last_run": ""})
        set_setting(db, WATCHLIST_KEY, {"entries": entries})
    return get_watchlist()


def watchlist_update(profile: str, enabled: bool | None = None, limit: int | None = None,
                     interval_hours: int | None = None) -> list[dict]:
    with _db_session() as db:
        data = get_setting(db, WATCHLIST_KEY)
        for e in data.get("entries", []):
            if e["profile"] == profile:
                if enabled is not None:
                    e["enabled"] = enabled
                if limit is not None:
                    e["limit"] = limit
                if interval_hours is not None:
                    e["interval_hours"] = interval_hours
                break
        set_setting(db, WATCHLIST_KEY, {"entries": data.get("entries", [])})
    return get_watchlist()


def watchlist_remove(profile: str) -> list[dict]:
    with _db_session() as db:
        data = get_setting(db, WATCHLIST_KEY)
        entries = [e for e in data.get("entries", []) if e["profile"] != profile]
        set_setting(db, WATCHLIST_KEY, {"entries": entries})
    return get_watchlist()


def run_due_watchlist(now: datetime | None = None) -> list[dict]:
    """Import from every due watchlist entry. Called by the worker cron."""
    now = now or datetime.now(timezone.utc)
    results = []
    for entry in get_watchlist():
        if not entry.get("enabled", True):
            continue
        interval = float(entry.get("interval_hours", 12)) * 3600
        last = entry.get("last_run") or ""
        if last:
            try:
                elapsed = (now - datetime.fromisoformat(last)).total_seconds()
                if elapsed < interval:
                    continue
            except ValueError:
                pass
        limit = int(entry.get("limit", 10))
        log.info("watchlist: importing @%s (limit %s)", entry["profile"], limit)
        res = import_job(entry["profile"], limit=limit)
        results.append({"profile": entry["profile"], **{k: res[k] for k in ("fetched", "queued", "failed")}})
        watchlist_update(entry["profile"])  # touch nothing; last_run set below
        with _db_session() as db:
            data = get_setting(db, WATCHLIST_KEY)
            for e in data.get("entries", []):
                if e["profile"] == entry["profile"]:
                    e["last_run"] = now.isoformat()
            set_setting(db, WATCHLIST_KEY, {"entries": data.get("entries", [])})
        time.sleep(10)
    return results


# ── small helper ─────────────────────────────────────────────────────────


def _db_session():
    from contextlib import contextmanager

    from memes_shared.db.session import SessionLocal

    @contextmanager
    def _ctx():
        with SessionLocal() as s:
            yield s
            s.commit()  # set_setting only flushes — persist service-owned writes

    return _ctx()
