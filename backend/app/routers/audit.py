"""Audit / automation / error logs."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from memes_shared.models import AuditLog, AutomationLog, ErrorLog
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.serializers import rows_to_dicts

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def all_logs(limit: int = 100, db: Session = Depends(get_db)):
    n = min(limit, 500)
    return {
        "audit": rows_to_dicts(db.query(AuditLog).order_by(AuditLog.id.desc()).limit(n).all()),
        "automation": rows_to_dicts(
            db.query(AutomationLog).order_by(AutomationLog.id.desc()).limit(n).all()
        ),
        "errors": rows_to_dicts(db.query(ErrorLog).order_by(ErrorLog.id.desc()).limit(n).all()),
    }


@router.get("/audit")
def audit_logs(limit: int = 100, db: Session = Depends(get_db)):
    return rows_to_dicts(
        db.query(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 500)).all()
    )


@router.get("/automation")
def automation_logs(limit: int = 100, db: Session = Depends(get_db)):
    return rows_to_dicts(
        db.query(AutomationLog).order_by(AutomationLog.id.desc()).limit(min(limit, 500)).all()
    )


@router.get("/errors")
def error_logs(limit: int = 100, db: Session = Depends(get_db)):
    return rows_to_dicts(
        db.query(ErrorLog).order_by(ErrorLog.id.desc()).limit(min(limit, 500)).all()
    )
