"""Global settings (rules / scheduler / trend / publishing / notifications)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from memes_shared.services.settings import get_all_settings, get_setting, set_setting

router = APIRouter(dependencies=[Depends(current_admin)])

ALLOWED_KEYS = {"automation", "rules", "scheduler", "trend", "publishing",
                "notifications", "discovery"}


@router.get("")
def read_settings(db: Session = Depends(get_db)):
    return get_all_settings(db)


@router.get("/{key}")
def read_key(key: str, db: Session = Depends(get_db)):
    if key not in ALLOWED_KEYS:
        raise HTTPException(404, "unknown settings key")
    return get_setting(db, key)


@router.put("/{key}")
def write_key(key: str, body: dict, db: Session = Depends(get_db)):
    if key not in ALLOWED_KEYS:
        raise HTTPException(404, "unknown settings key")
    if key == "automation":
        raise HTTPException(400, "automation state is controlled via /automation endpoints")
    merged = set_setting(db, key, body)
    db.commit()
    return merged
