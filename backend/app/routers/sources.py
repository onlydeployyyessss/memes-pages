"""Content sources — the authorization system."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.schemas import SourceIn, SourcePatchIn
from backend.app.serializers import to_dict
from memes_shared.models import ContentSource
from memes_shared.services.discovery import discover_source

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def list_sources(db: Session = Depends(get_db)):
    rows = db.query(ContentSource).order_by(ContentSource.priority, ContentSource.id).all()
    return {"items": [to_dict(r) for r in rows], "total": len(rows)}


@router.post("", status_code=201)
def create_source(body: SourceIn, db: Session = Depends(get_db)):
    if body.source_type not in ("rss", "authorized_feed", "agent_reach", "manual", "webhook", "telegram"):
        raise HTTPException(422, "invalid source_type")
    if body.authorization not in ("authorized", "not_authorized", "disabled"):
        raise HTTPException(422, "authorization must be authorized | not_authorized | disabled")
    src = ContentSource(**body.model_dump())
    db.add(src)
    db.commit()
    return to_dict(src)


@router.get("/{source_id}")
def get_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(ContentSource, source_id)
    if src is None:
        raise HTTPException(404, "Source not found")
    return to_dict(src)


@router.patch("/{source_id}")
def patch_source(source_id: int, body: SourcePatchIn, db: Session = Depends(get_db)):
    src = db.get(ContentSource, source_id)
    if src is None:
        raise HTTPException(404, "Source not found")
    if body.authorization is not None and body.authorization not in (
        "authorized", "not_authorized", "disabled"
    ):
        raise HTTPException(422, "invalid authorization value")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(src, field, value)
    db.commit()
    return to_dict(src)


@router.post("/{source_id}/authorize")
def authorize(source_id: int, body: dict, db: Session = Depends(get_db)):
    src = db.get(ContentSource, source_id)
    if src is None:
        raise HTTPException(404, "Source not found")
    value = body.get("authorization", "authorized")
    if value not in ("authorized", "not_authorized", "disabled"):
        raise HTTPException(422, "invalid authorization value")
    src.authorization = value
    db.commit()
    return {"source_id": src.id, "authorization": src.authorization}


@router.delete("/{source_id}")
def delete_source(source_id: int, db: Session = Depends(get_db)):
    src = db.get(ContentSource, source_id)
    if src is None:
        raise HTTPException(404, "Source not found")
    db.delete(src)
    db.commit()
    return {"ok": True}


@router.post("/{source_id}/check")
def check_now(source_id: int, db: Session = Depends(get_db)):
    """Trigger discovery for one source immediately."""
    src = db.get(ContentSource, source_id)
    if src is None:
        raise HTTPException(404, "Source not found")
    created, skipped = discover_source(db, src)
    db.commit()
    return {"source_id": src.id, "created": created, "skipped": skipped}
