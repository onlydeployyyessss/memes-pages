"""Captions, caption templates."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.schemas import CaptionIn, CaptionTemplateIn
from backend.app.serializers import to_dict
from memes_shared.models import Caption, CaptionTemplate, DestinationAccount

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def list_captions(db: Session = Depends(get_db)):
    rows = db.query(Caption).order_by(Caption.id).all()
    return {"items": [to_dict(r) for r in rows], "total": len(rows)}


@router.post("", status_code=201)
def create_caption(body: CaptionIn, db: Session = Depends(get_db)):
    if body.is_default:
        for c in db.query(Caption).filter_by(is_default=True):
            c.is_default = False
    row = Caption(**body.model_dump())
    db.add(row)
    db.commit()
    return to_dict(row)


@router.patch("/{caption_id}")
def patch_caption(caption_id: int, body: dict, db: Session = Depends(get_db)):
    row = db.get(Caption, caption_id)
    if row is None:
        raise HTTPException(404, "Caption not found")
    for field in ("name", "text", "hashtags", "is_default", "language"):
        if field in body:
            if field == "is_default" and body[field]:
                for c in db.query(Caption).filter_by(is_default=True):
                    c.is_default = False
            setattr(row, field, body[field])
    db.commit()
    return to_dict(row)


@router.post("/{caption_id}/make-default")
def make_default(caption_id: int, db: Session = Depends(get_db)):
    row = db.get(Caption, caption_id)
    if row is None:
        raise HTTPException(404, "Caption not found")
    for c in db.query(Caption).filter_by(is_default=True):
        c.is_default = False
    row.is_default = True
    db.commit()
    return to_dict(row)


@router.delete("/{caption_id}")
def delete_caption(caption_id: int, db: Session = Depends(get_db)):
    row = db.get(Caption, caption_id)
    if row is None:
        raise HTTPException(404, "Caption not found")
    used = db.query(DestinationAccount).filter_by(default_caption_id=caption_id).count()
    if used:
        raise HTTPException(409, "caption is assigned to accounts — unassign first")
    db.delete(row)
    db.commit()
    return {"ok": True}


# ── Templates ────────────────────────────────────────────────────────
@router.get("/templates")
def list_templates(db: Session = Depends(get_db)):
    rows = db.query(CaptionTemplate).order_by(CaptionTemplate.id).all()
    return {"items": [to_dict(r) for r in rows], "total": len(rows)}


@router.post("/templates", status_code=201)
def create_template(body: CaptionTemplateIn, db: Session = Depends(get_db)):
    row = CaptionTemplate(**body.model_dump())
    db.add(row)
    db.commit()
    return to_dict(row)


@router.patch("/templates/{template_id}")
def patch_template(template_id: int, body: dict, db: Session = Depends(get_db)):
    row = db.get(CaptionTemplate, template_id)
    if row is None:
        raise HTTPException(404, "Template not found")
    for field in ("name", "template_text", "placeholder_keys", "weight", "enabled"):
        if field in body:
            setattr(row, field, body[field])
    db.commit()
    return to_dict(row)


@router.delete("/templates/{template_id}")
def delete_template(template_id: int, db: Session = Depends(get_db)):
    row = db.get(CaptionTemplate, template_id)
    if row is None:
        raise HTTPException(404, "Template not found")
    db.delete(row)
    db.commit()
    return {"ok": True}


@router.post("/preview")
def preview(body: dict, db: Session = Depends(get_db)):
    """Render a template/hashtag combo with sample context."""
    from memes_shared.services.captions import build_caption

    text = build_caption(
        mode=body.get("mode", "custom"),
        custom_text=body.get("template_text", ""),
        hashtags=body.get("hashtags") or [],
        context=body.get("context") or {"title": "Sample viral video", "author": "creator",
                                        "account": "@yourpage", "category": "memes"},
    )
    return {"preview": text}
