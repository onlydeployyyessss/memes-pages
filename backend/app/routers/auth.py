"""Admin authentication: JWT login, bootstrap registration, admins CRUD."""
from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from backend.app.deps import current_admin, get_db, get_client_ip, require_role
from backend.app.schemas import AdminCreateIn, LoginIn, PasswordChangeIn
from backend.app.serializers import to_dict
from memes_shared.models import AdminUser, AuditLog
from memes_shared.security import create_access_token, hash_password, verify_password
from memes_shared.utils.timeutil import utcnow

router = APIRouter()
bearer = HTTPBearer(auto_error=False)


def _audit(db: Session, request: Request, action: str, admin: AdminUser | None = None, details: dict | None = None):
    db.add(AuditLog(
        actor_type="admin",
        actor_id=str(admin.id) if admin else "",
        action=action,
        entity_type="admin_user",
        entity_id=str(admin.id) if admin else "",
        details=details or {},
        ip=get_client_ip(request),
    ))


def _token(admin: AdminUser) -> dict:
    return {
        "access_token": create_access_token(
            admin.id, {"role": admin.role, "email": admin.email},
            expires_minutes=12 * 60,
        ),
        "token_type": "bearer",
        "expires_in": int(timedelta(minutes=12 * 60).total_seconds()),
        "admin": to_dict(admin, exclude={"password_hash"}),
    }


@router.post("/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    admin = db.query(AdminUser).filter_by(email=body.email.lower()).first()
    if admin is None or not verify_password(body.password, admin.password_hash):
        raise HTTPException(401, "Invalid email or password")
    if not admin.is_active:
        raise HTTPException(403, "Account disabled")
    admin.last_login_at = utcnow()
    _audit(db, request, "login", admin)
    db.commit()
    return _token(admin)


@router.post("/register")
def register(body: AdminCreateIn, request: Request, db: Session = Depends(get_db)):
    """Bootstrap: first admin can self-register; afterwards owner-only."""
    count = db.query(AdminUser).count()
    if count > 0:
        raise HTTPException(403, "Registration closed — ask an owner to create accounts")
    if body.role != "owner":
        body.role = "owner"
    admin = AdminUser(
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        full_name=body.full_name or "Owner",
        role="owner",
    )
    db.add(admin)
    db.commit()
    return _token(admin)


@router.get("/me")
def me(admin: AdminUser = Depends(current_admin)):
    return to_dict(admin, exclude={"password_hash"})


@router.put("/password")
def change_password(body: PasswordChangeIn, request: Request,
                    admin: AdminUser = Depends(current_admin),
                    db: Session = Depends(get_db)):
    if not verify_password(body.current_password, admin.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    admin.password_hash = hash_password(body.new_password)
    _audit(db, request, "password_change", admin)
    db.commit()
    return {"ok": True}


@router.get("/admins")
def list_admins(admin: AdminUser = Depends(require_role("owner")),
                db: Session = Depends(get_db)):
    return [to_dict(a, exclude={"password_hash"}) for a in db.query(AdminUser).all()]


@router.post("/admins")
def create_admin(body: AdminCreateIn, request: Request,
                 admin: AdminUser = Depends(require_role("owner")),
                 db: Session = Depends(get_db)):
    if db.query(AdminUser).filter_by(email=body.email.lower()).first():
        raise HTTPException(409, "Email already registered")
    row = AdminUser(
        email=body.email.lower(), password_hash=hash_password(body.password),
        full_name=body.full_name, role=body.role if body.role in ("owner", "admin", "viewer") else "admin",
    )
    db.add(row)
    _audit(db, request, "admin_create", admin, {"new_admin_id": row.id, "role": row.role})
    db.commit()
    db.refresh(row)
    return to_dict(row, exclude={"password_hash"})


@router.patch("/admins/{admin_id}")
def patch_admin(admin_id: int, body: dict, request: Request,
                admin: AdminUser = Depends(require_role("owner")),
                db: Session = Depends(get_db)):
    row = db.get(AdminUser, admin_id)
    if row is None:
        raise HTTPException(404, "Admin not found")
    for field in ("full_name", "role", "is_active"):
        if field in body:
            setattr(row, field, body[field])
    _audit(db, request, "admin_update", admin, {"target": admin_id, "fields": list(body)})
    db.commit()
    return to_dict(row, exclude={"password_hash"})
