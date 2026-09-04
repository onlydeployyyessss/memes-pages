"""Shared FastAPI dependencies: DB session, auth, rate limiting."""
from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Iterator

import jwt as pyjwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from memes_shared.db.session import SessionLocal
from memes_shared.models import AdminUser
from sqlalchemy.orm import Session

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def current_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> AdminUser:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    from memes_shared.security import decode_token

    try:
        payload = decode_token(credentials.credentials)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except pyjwt.InvalidTokenError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    admin = db.get(AdminUser, int(payload.get("sub", 0)))
    if admin is None or not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin account disabled")
    return admin


def require_role(*roles: str):
    def checker(admin: AdminUser = Depends(current_admin)) -> AdminUser:
        if roles and admin.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN,
                                f"Requires role: {' / '.join(roles)}")
        return admin
    return checker


# ── Simple per-IP sliding-window rate limiter ────────────────────────
class RateLimiter:
    def __init__(self, limit: str = "120/minute"):
        amount, _, period = limit.partition("/")
        self.amount = int(amount) if amount.isdigit() else 120
        self.window = {"second": 1, "minute": 60, "hour": 3600}.get(period.strip(), 60)
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> bool:
        now = time.monotonic()
        q = self.hits[key]
        while q and q[0] < now - self.window:
            q.popleft()
        if len(q) >= self.amount:
            return False
        q.append(now)
        return True

    @property
    def headers(self) -> dict:
        return {"Retry-After": str(self.window)}


def get_client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return (fwd.split(",")[0].strip() if fwd else None) or (
        request.client.host if request.client else "unknown"
    )
