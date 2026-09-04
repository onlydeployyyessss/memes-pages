"""InstaLoader endpoints — thin layer over shared/services/instaloader_service.

Manual imports run in a background thread with live status (JOB);
the watchlist (auto-import) is executed by the worker cron and only
configured here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from threading import Thread

from fastapi import APIRouter, Depends, HTTPException
from memes_shared.services import instaloader_service as svc
from pydantic import BaseModel, Field

from backend.app.deps import current_admin

router = APIRouter(dependencies=[Depends(current_admin)])

JOB: dict = {"running": False, "profile": "", "fetched": 0, "queued": 0, "failed": 0,
             "messages": [], "started_at": "", "finished_at": ""}
_CANCEL = False


class SessionImportIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    sessionid: str = Field(min_length=20, max_length=600)


class GraphTokenIn(BaseModel):
    token: str = Field(min_length=40, max_length=800)


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class FetchIn(BaseModel):
    profile: str = Field(min_length=1, max_length=60)
    limit: int = Field(default=10, ge=1, le=svc.MAX_PER_JOB)
    sleep_seconds: float = Field(default=svc.DEFAULT_SLEEP_S, ge=2.0, le=30.0)


class WatchlistIn(BaseModel):
    profile: str = Field(min_length=1, max_length=60)
    limit: int = Field(default=10, ge=1, le=svc.MAX_PER_JOB)
    interval_hours: int = Field(default=12, ge=1, le=168)


# ── sessions ─────────────────────────────────────────────────────────────

@router.post("/login")
def login(body: LoginIn):
    try:
        res = svc.login_save(body.username.strip(), body.password)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"ok": True, **res,
            "message": "session saved encrypted — reused automatically (password never stored)"}


@router.post("/session-import")
def session_import(body: SessionImportIn):
    try:
        res = svc.import_session(body.username.strip(), body.sessionid)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    return {"ok": True, **res, "message": "session imported from your browser — reused automatically"}


@router.post("/graph-token")
def graph_token_save_ep(body: GraphTokenIn):
    svc.graph_token_save(body.token)
    return {"ok": True, "message": "Graph token stored encrypted — instaloader 429s now fall back to official business_discovery"}


@router.get("/status")
def status():
    return {"job": JOB, "sessions": svc.list_sessions(), "watchlist": svc.get_watchlist()}


@router.delete("/session/{username}")
def delete_session(username: str):
    return {"ok": True, "removed": svc.remove_session(username)}


# ── manual import ────────────────────────────────────────────────────────

@router.post("/fetch")
def fetch(body: FetchIn):
    global JOB, _CANCEL
    if JOB["running"]:
        raise HTTPException(409, "an import job is already running — check status or cancel it")
    _CANCEL = False
    profile = body.profile.strip().lstrip("@").split("/")[0]

    def _progress(s: dict) -> None:
        JOB.clear()
        JOB.update(s)

    def _cancel() -> bool:
        return _CANCEL

    JOB.update({"running": True, "profile": profile, "fetched": 0, "queued": 0,
                "failed": 0, "messages": [], "started_at": datetime.now(timezone.utc).isoformat(),
                "finished_at": ""})
    Thread(target=svc.import_job, kwargs={
        "profile": profile, "limit": body.limit, "sleep_s": body.sleep_seconds,
        "progress": _progress, "cancel_check": _cancel}, daemon=True).start()
    return {"ok": True, "job": JOB,
            "note": "running in background — poll GET /instaloader/status or watch the Content page"}


@router.post("/cancel")
def cancel():
    global _CANCEL
    if not JOB.get("running"):
        return {"ok": True, "note": "no job running"}
    _CANCEL = True
    JOB["messages"].append("🛑 cancel requested — stopping at the next checkpoint")
    return {"ok": True, "note": "cancel signalled"}


# ── watchlist (daily auto-import, run by the worker) ─────────────────────

@router.get("/watchlist")
def watchlist_get():
    return {"entries": svc.get_watchlist()}


@router.post("/watchlist")
def watchlist_add(body: WatchlistIn):
    entries = svc.watchlist_add(body.profile, limit=body.limit, interval_hours=body.interval_hours)
    return {"ok": True, "entries": entries}


@router.patch("/watchlist/{profile}")
def watchlist_patch(profile: str, enabled: bool | None = None, limit: int | None = None,
                    interval_hours: int | None = None):
    entries = svc.watchlist_update(profile, enabled=enabled, limit=limit, interval_hours=interval_hours)
    return {"ok": True, "entries": entries}


@router.delete("/watchlist/{profile}")
def watchlist_delete(profile: str):
    return {"ok": True, "entries": svc.watchlist_remove(profile)}
