"""Internal media ingest — worker pushes processed media to the api store.

Auth: X-Ingest-Key must equal MEMES_SECRET_KEY (shared secret). Paths are
restricted to <media>/videos and <media>/covers (no traversal).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger

from backend.app.deps import get_client_ip

log = get_logger("memes.media")

router = APIRouter()


def _authorized(request: Request) -> None:
    key = request.headers.get("X-Ingest-Key", "")
    if not key or key != get_settings().secret_key:
        raise HTTPException(401, "invalid ingest key")


@router.post("/ingest", dependencies=[Depends(_authorized)])
async def ingest(request: Request, file: UploadFile = File(...), rel_path: str = Form(...)):
    cfg = get_settings()
    media_root = cfg.media_path.resolve()
    dest = (media_root / rel_path).resolve()
    allowed = (media_root / "videos").resolve(), (media_root / "covers").resolve()
    if not any(dest.parent == a for a in allowed):
        raise HTTPException(422, "rel_path must be videos/<name> or covers/<name>")
    dest.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    with open(dest, "wb") as f:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > 520 * 1024 * 1024:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "ingest file exceeds 500 MB")
            f.write(chunk)
    log.info("ingested %s (%s bytes) from %s", rel_path, size, get_client_ip(request))
    return {"ok": True, "path": rel_path, "size": size}
