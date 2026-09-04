"""Destination accounts CRUD + settings + credentials + metrics."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from memes_shared.models import AccountMetrics, AccountSettings, DailyMetric, DestinationAccount
from memes_shared.security import encrypt_credential
from memes_shared.services import metrics as metrics_svc
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.schemas import AccountIn, AccountPatchIn, AccountSettingsIn, CredentialsIn
from backend.app.serializers import rows_to_dicts, to_dict

router = APIRouter(dependencies=[Depends(current_admin)])


def _get(db: Session, account_id: int) -> DestinationAccount:
    acc = db.get(DestinationAccount, account_id)
    if acc is None:
        raise HTTPException(404, "Account not found")
    return acc


def _ensure_settings(db: Session, account: DestinationAccount) -> AccountSettings:
    st = account.settings
    if st is None:
        st = AccountSettings(
            account_id=account.id,
            caption_settings={"mode": "default", "custom_text": "", "hashtags": [], "first_comment": ""},
            cover_settings={"mode": "account", "cover_id": None},
            schedule_settings={},
            posting_limits={"max_per_day": 10, "max_per_hour": 3},
            distribution={"enabled": True, "categories": [], "keywords": [], "publish_delay_minutes": 0},
        )
        db.add(st)
        db.flush()
        db.refresh(account)
    return st


@router.get("")
def list_accounts(db: Session = Depends(get_db)):
    accounts = db.query(DestinationAccount).order_by(DestinationAccount.id).all()
    out = []
    for acc in accounts:
        d = to_dict(acc, exclude={"credentials_enc"})
        d["has_credentials"] = bool(acc.credentials_enc)
        out.append(d)
    return {"items": out, "total": len(out)}


@router.post("", status_code=201)
def create_account(body: AccountIn, db: Session = Depends(get_db)):
    acc = DestinationAccount(**body.model_dump())
    db.add(acc)
    db.flush()
    _ensure_settings(db, acc)
    db.commit()
    return to_dict(acc, exclude={"credentials_enc"})


@router.get("/{account_id}")
def get_account(account_id: int, db: Session = Depends(get_db)):
    acc = _get(db, account_id)
    d = to_dict(acc, exclude={"credentials_enc"})
    d["settings"] = to_dict(_ensure_settings(db, acc), exclude={"id", "account_id", "created_at", "updated_at"})
    return d


@router.patch("/{account_id}")
def patch_account(account_id: int, body: AccountPatchIn, db: Session = Depends(get_db)):
    acc = _get(db, account_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(acc, field, value)
    db.commit()
    return to_dict(acc, exclude={"credentials_enc"})


@router.delete("/{account_id}")
def delete_account(account_id: int, db: Session = Depends(get_db)):
    acc = _get(db, account_id)
    db.delete(acc)
    db.commit()
    return {"ok": True, "deleted": account_id}


@router.post("/{account_id}/automation")
def toggle_automation(account_id: int, body: dict, db: Session = Depends(get_db)):
    acc = _get(db, account_id)
    acc.automation_enabled = bool(body.get("enabled", True))
    db.commit()
    return {"account_id": acc.id, "automation_enabled": acc.automation_enabled}


@router.put("/{account_id}/settings")
def put_settings(account_id: int, body: AccountSettingsIn, db: Session = Depends(get_db)):
    acc = _get(db, account_id)
    st = _ensure_settings(db, acc)
    for field in ("caption_settings", "cover_settings", "schedule_settings",
                  "posting_limits", "distribution"):
        value = getattr(body, field)
        if value is not None:
            setattr(st, field, value)
    db.commit()
    return to_dict(st, exclude={"id", "account_id", "created_at", "updated_at"})


@router.post("/{account_id}/credentials")
def put_credentials(account_id: int, body: CredentialsIn, db: Session = Depends(get_db)):
    """Store platform credentials encrypted-at-rest (never returned)."""
    acc = _get(db, account_id)
    blob = encrypt_credential(json.dumps(body.credentials))
    acc.credentials_enc = blob
    acc.integration_status = "connected" if body.credentials else "not_connected"
    db.commit()
    return {"account_id": acc.id, "integration_status": acc.integration_status,
            "keys_stored": sorted(body.credentials.keys())}


@router.post("/{account_id}/metrics/refresh")
def refresh_metrics(account_id: int, db: Session = Depends(get_db)):
    acc = _get(db, account_id)
    result = metrics_svc.refresh_account_metrics(db, acc)
    db.commit()
    return result


@router.get("/{account_id}/metrics")
def get_metrics(account_id: int, days: int = 30, db: Session = Depends(get_db)):
    _get(db, account_id)
    daily = (
        db.query(DailyMetric)
        .filter(DailyMetric.account_id == account_id)
        .order_by(DailyMetric.date.desc())
        .limit(days)
        .all()
    )
    samples = (
        db.query(AccountMetrics)
        .filter(AccountMetrics.account_id == account_id)
        .order_by(AccountMetrics.captured_at.desc())
        .limit(50)
        .all()
    )
    return {"daily": rows_to_dicts(daily), "samples": rows_to_dicts(samples)}
