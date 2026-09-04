"""Health & readiness."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.deps import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "error"}
