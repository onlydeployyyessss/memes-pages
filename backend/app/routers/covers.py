"""Reel covers: upload, set default, assign to accounts, preview."""
from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.serializers import to_dict
from memes_shared.config import get_settings
from memes_shared.models import DestinationAccount, ReelCover

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def list_covers(db: Session = Depends(get_db)):
    rows = db.query(ReelCover).order_by(ReelCover.id).all()
    return {"items": [to_dict(r) for r in rows], "total": len(rows)}


@router.post("", status_code=201)
def upload_cover(file: UploadFile = File(...), name: str = "", db: Session = Depends(get_db)):
    suffix = "." + (file.filename or "cover.jpg").rsplit(".", 1)[-1].lower()
    if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
        raise HTTPException(422, "cover must be jpg/png/webp")
    covers_dir = get_settings().media_path / "covers"
    covers_dir.mkdir(parents=True, exist_ok=True)
    filename = f"cover_{uuid.uuid4().hex[:12]}{suffix}"
    dest = covers_dir / filename
    size = 0
    with open(dest, "wb") as f:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > 20 * 1024 * 1024:
                f.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, "cover exceeds 20 MB")
            f.write(chunk)
    width = height = 0
    try:
        with Image.open(dest) as im:
            width, height = im.size
    except Exception:  # noqa: BLE001
        pass
    row = ReelCover(name=name or (file.filename or "cover"), file_path=str(dest),
                    file_size=size, width=width, height=height)
    db.add(row)
    db.commit()
    return to_dict(row)


@router.get("/{cover_id}")
def get_cover(cover_id: int, db: Session = Depends(get_db)):
    row = db.get(ReelCover, cover_id)
    if row is None:
        raise HTTPException(404, "Cover not found")
    d = to_dict(row)
    d["url"] = f"/media/covers/{Path(row.file_path).name}"
    return d


@router.patch("/{cover_id}")
def patch_cover(cover_id: int, body: dict, db: Session = Depends(get_db)):
    row = db.get(ReelCover, cover_id)
    if row is None:
        raise HTTPException(404, "Cover not found")
    if body.get("is_default"):
        for c in db.query(ReelCover).filter_by(is_default=True):
            c.is_default = False
        row.is_default = True
    if "name" in body:
        row.name = body["name"]
    db.commit()
    return to_dict(row)


@router.post("/{cover_id}/assign")
def assign_cover(cover_id: int, body: dict, db: Session = Depends(get_db)):
    row = db.get(ReelCover, cover_id)
    if row is None:
        raise HTTPException(404, "Cover not found")
    account = db.get(DestinationAccount, int(body.get("account_id", 0)))
    if account is None:
        raise HTTPException(404, "Account not found")
    account.reel_cover_id = cover_id
    if account.settings is None:
        from memes_shared.models import AccountSettings

        db.add(AccountSettings(account_id=account.id,
                               cover_settings={"mode": "account", "cover_id": cover_id}))
    else:
        account.settings.cover_settings = {"mode": "account", "cover_id": cover_id}
    db.commit()
    return {"account_id": account.id, "cover_id": cover_id}


@router.delete("/{cover_id}")
def delete_cover(cover_id: int, db: Session = Depends(get_db)):
    row = db.get(ReelCover, cover_id)
    if row is None:
        raise HTTPException(404, "Cover not found")
    used = db.query(DestinationAccount).filter_by(reel_cover_id=cover_id).count()
    if used:
        raise HTTPException(409, "cover assigned to accounts — unassign first")
    db.delete(row)
    db.commit()
    return {"ok": True}
