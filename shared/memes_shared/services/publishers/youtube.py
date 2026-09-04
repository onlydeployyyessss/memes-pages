"""YouTube Shorts publisher — official YouTube Data API v3 (resumable upload).

creds = {"access_token": "...", }  (or refresh_token + client_id/secret and
this publisher will refresh automatically)
"""
from __future__ import annotations

import httpx

from memes_shared.logging_setup import get_logger
from memes_shared.models import DestinationAccount, PublishingJob
from memes_shared.services.publishers.base import PublishResult, Publisher, http_error_type

log = get_logger("memes.publishers.youtube")

UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
API = "https://www.googleapis.com/youtube/v3"
OAUTH = "https://oauth2.googleapis.com/token"
CHUNK = 8 * 1024 * 1024


class YouTubePublisher(Publisher):
    name = "youtube"

    def publish(self, *, video_path: str, caption: str, cover_path: str,
                account: DestinationAccount, job: PublishingJob, creds: dict) -> PublishResult:
        token = creds.get("access_token", "")
        if not token and creds.get("refresh_token") and creds.get("client_id"):
            token, err = _refresh(creds)
            if err:
                return PublishResult(success=False, error=err, error_type="auth")
        if not token:
            return PublishResult(success=False,
                                 error="YouTube credentials missing (access_token / refresh token)",
                                 error_type="config")

        from pathlib import Path

        p = Path(video_path)
        if not p.exists():
            return PublishResult(success=False, error=f"video missing: {video_path}",
                                 error_type="invalid")

        caption = (caption or "").strip()
        title = caption.splitlines()[0][:95] if caption else f"Reel {job.id}"
        description = caption[:4900]
        meta = {
            "snippet": {"title": title, "description": description, "categoryId": "24"},
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        size = p.stat().st_size
        with open(p, "rb") as f, httpx.Client(timeout=120.0) as client:
            resp = client.post(
                f"{UPLOAD}?uploadType=resumable&part=snippet,status",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Upload-Content-Length": str(size),
                    "X-Upload-Content-Type": "video/mp4",
                },
                json=meta,
            )
            if resp.status_code >= 400:
                return _fail(resp.status_code, resp.text, "upload init failed")
            location = resp.headers.get("location")
            if not location:
                return PublishResult(success=False, error="no upload location returned",
                                     error_type="invalid")

            offset = 0
            while True:
                chunk = f.read(CHUNK)
                headers = {
                    "Authorization": f"Bearer {token}",
                    "Content-Length": str(len(chunk)) if chunk else "0",
                    "Content-Range": f"bytes {offset}-{offset + len(chunk) - 1}/{size}" if chunk
                    else f"bytes */{size}",
                }
                resp = client.put(location, content=chunk or b"", headers=headers)
                if resp.status_code in (200, 201):
                    body = resp.json()
                    vid = body.get("id", "")
                    log.info("uploaded YouTube video %s (%.1f MB)", vid, size / 1e6)
                    return PublishResult(
                        success=True, external_id=vid,
                        permalink=f"https://youtube.com/shorts/{vid}", raw=body,
                    )
                if resp.status_code == 308:
                    rng = resp.headers.get("range", "")
                    if rng:
                        offset = int(rng.split("-")[1]) + 1
                        f.seek(offset)
                    else:
                        offset += len(chunk)
                    continue
                return _fail(resp.status_code, resp.text, "upload failed")


def _refresh(creds: dict) -> tuple[str, str]:
    data = {
        "client_id": creds.get("client_id", ""),
        "client_secret": creds.get("client_secret", ""),
        "refresh_token": creds.get("refresh_token", ""),
        "grant_type": "refresh_token",
    }
    try:
        resp = httpx.post(OAUTH, data=data, timeout=30.0)
        body = resp.json()
        if resp.status_code >= 400:
            return "", f"token refresh failed: {body.get('error_description', body)}"
        return body.get("access_token", ""), ""
    except httpx.HTTPError as e:
        return "", f"token refresh network error: {e}"


def _fail(status: int, text: str, context: str) -> PublishResult:
    return PublishResult(success=False, error=f"{context}: HTTP {status} {text[:300]}",
                         error_type=http_error_type(status, text))
