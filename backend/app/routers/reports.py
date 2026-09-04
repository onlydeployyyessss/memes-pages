"""Reports: list, detail, generate."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db
from backend.app.serializers import to_dict
from memes_shared.models import Report
from memes_shared.services.reports import generate_report

router = APIRouter(dependencies=[Depends(current_admin)])


@router.get("")
def list_reports(limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(Report)
        .order_by(Report.id.desc())
        .limit(min(limit, 200))
        .all()
    )
    return {"items": [to_dict(r, exclude={"text_content", "payload"}) for r in rows]}


@router.get("/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    row = db.get(Report, report_id)
    if row is None:
        raise HTTPException(404, "Report not found")
    return to_dict(row)


@router.post("/generate")
def generate(body: dict, db: Session = Depends(get_db)):
    rtype = body.get("type", "daily")
    if rtype not in ("daily", "weekly", "monthly", "network", "account"):
        raise HTTPException(422, "type must be daily|weekly|monthly|network|account")
    report = generate_report(
        db, rtype, account_id=body.get("account_id"), send=bool(body.get("send", False))
    )
    db.commit()
    return to_dict(report)
