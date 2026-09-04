"""Health & readiness."""
from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from backend.app.deps import get_db  # noqa: F401
from fastapi import Depends
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "error"}
