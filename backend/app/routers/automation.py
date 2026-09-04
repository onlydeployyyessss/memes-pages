"""Automation control: start / pause / resume / stop / run-now / status."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from memes_shared.models import AuditLog
from memes_shared.services import automation
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("/status")
def status(db: Session = Depends(get_db)):
    return automation.status_summary(db)


@router.post("/start")
def start(db: Session = Depends(get_db), admin=Depends(current_admin)):
    state = automation.start(db)
    db.add(AuditLog(actor_type="admin", actor_id=str(admin.id), action="automation_start"))
    db.commit()
    return state


@router.post("/pause")
def pause(db: Session = Depends(get_db), admin=Depends(current_admin)):
    state = automation.pause(db)
    db.add(AuditLog(actor_type="admin", actor_id=str(admin.id), action="automation_pause"))
    db.commit()
    return state


@router.post("/resume")
def resume(db: Session = Depends(get_db), admin=Depends(current_admin)):
    state = automation.resume(db)
    db.add(AuditLog(actor_type="admin", actor_id=str(admin.id), action="automation_resume"))
    db.commit()
    return state


@router.post("/stop")
def stop(db: Session = Depends(get_db), admin=Depends(current_admin)):
    state = automation.stop(db)
    db.add(AuditLog(actor_type="admin", actor_id=str(admin.id), action="automation_stop"))
    db.commit()
    return state


@router.post("/run-now")
def run_now(db: Session = Depends(get_db), admin=Depends(current_admin)):
    """Ask the worker to run a full automation cycle immediately."""
    state = automation.request_run(db)
    db.add(AuditLog(actor_type="admin", actor_id=str(admin.id), action="automation_run_now"))
    db.commit()
    return {"run_requested": True, "state": state}
