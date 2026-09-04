"""Instagram Reels publisher — official Instagram Graph API only.

Requires: Instagram Business/Creator account linked to a Facebook Page,
a Meta app with instagram_content_publish permission, and the account's
access token + IG user id stored (encrypted) in the destination account:
    creds = {"access_token": "...", "ig_user_id": "..."}
Video must be reachable at a public URL (MEMES_PUBLIC_MEDIA_BASE_URL).
"""
from __future__ import annotations

import time

import httpx

from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger
from memes_shared.models import DestinationAccount, PublishingJob
from memes_shared.services.publishers.base import Publisher, PublishResult

log = get_logger("memes.publishers.instagram")

GRAPH_FB = "https://graph.facebook.com/v21.0"
GRAPH_IG = "https://graph.instagram.com/v21.0"


def api_base(token: str) -> str:
    """Instagram-hosted tokens (IG*) speak to graph.instagram.com; FB tokens to graph.facebook.com."""
    return GRAPH_IG if token.startswith(("IGAA", "IGQ", "IGD", "IGSC")) else GRAPH_FB


class InstagramPublisher(Publisher):
    name = "instagram"

    def publish(self, *, video_path: str, caption: str, cover_path: str,
                account: DestinationAccount, job: PublishingJob, creds: dict) -> PublishResult:
        token = creds.get("access_token", "")
        ig_user_id = creds.get("ig_user_id", "") or account.external_id
        if not token or not ig_user_id:
            return PublishResult(
                success=False,
                error="Instagram credentials missing — store {access_token, ig_user_id} on the account",
                error_type="config",
            )
        base = get_settings().public_media_base_url.rstrip("/")
        if not base:
            return PublishResult(
                success=False,
                error="MEMES_PUBLIC_MEDIA_BASE_URL is not configured — Graph API needs a public video URL",
                error_type="config",
            )
        # stored videos live at <media base>/videos/<filename>
        video_url = f"{base}/videos/{video_path.split('/')[-1]}"
        cover_url = f"{base}/covers/{cover_path.split('/')[-1]}" if cover_path else ""

        with httpx.Client(timeout=60.0) as client:
            # 1. create media container
            payload: dict = {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": (caption or "")[:2200],
                "access_token": token,
            }
            if cover_url:
                payload["cover_url"] = cover_url
            graph = api_base(token)
            resp = client.post(f"{graph}/{ig_user_id}/media", data=payload)
            body = _json(resp)
            if resp.status_code >= 400:
                return _fail(resp.status_code, body, "container creation failed")
            container_id = body.get("id", "")
            if not container_id:
                return PublishResult(success=False, error="no container id returned",
                                     error_type="invalid", raw=body)

            # 2. wait for processing (official status endpoint)
            ok, err = _wait_container(client, graph, container_id, token)
            if not ok:
                return PublishResult(success=False, error=err, error_type="transient",
                                     raw={"container_id": container_id})

            # 3. publish
            resp = client.post(
                f"{graph}/{ig_user_id}/media_publish",
                data={"creation_id": container_id, "access_token": token},
            )
            body = _json(resp)
            if resp.status_code >= 400:
                return _fail(resp.status_code, body, "media_publish failed")
            post_id = body.get("id", "")
            return PublishResult(
                success=True,
                external_id=post_id,
                permalink=f"https://www.instagram.com/reel/{post_id}/",
                raw=body,
            )


def _json(resp: httpx.Response) -> dict:
    try:
        return resp.json()
    except Exception:
        return {"raw": resp.text[:500]}


def _fail(status: int, body: dict, context: str) -> PublishResult:
    err = (body.get("error") or {})
    msg = f"{context}: {err.get('message', body)}"
    code = err.get("code", 0)
    if code in (4, 32, 613) or status == 429:
        etype = "rate_limit"
    elif status in (401, 403) or code in (190, 102):
        etype = "auth"
    elif status >= 500:
        etype = "transient"
    else:
        etype = "invalid"
    return PublishResult(success=False, error=msg, error_type=etype, raw=body)


def _wait_container(client: httpx.Client, graph: str, container_id: str, token: str,
                    timeout_s: int = 300) -> tuple[bool, str]:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"{graph}/{container_id}",
                          params={"fields": "status_code", "access_token": token})
        body = _json(resp)
        status = body.get("status_code", "")
        if status == "FINISHED":
            return True, ""
        if status in ("ERROR", "EXPIRED"):
            return False, f"container {status}"
        time.sleep(5)
    return False, "container processing timeout"
