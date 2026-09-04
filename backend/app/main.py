"""Memes Pages API — FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger, setup_logging

setup_logging()
log = get_logger("memes.api")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """SQLite dev/preview mode: auto-create schema + bootstrap admin.

    PostgreSQL deployments run Alembic migrations via the container
    entrypoint instead (see docker-compose backend command).
    """
    cfg = get_settings()
    if cfg.effective_database_url.startswith("sqlite"):
        import memes_shared.models  # noqa: F401 — register tables
        from memes_shared.db.base import Base
        from memes_shared.db.session import SessionLocal, get_engine
        from memes_shared.models import AdminUser
        from memes_shared.security import hash_password
        from memes_shared.services.settings import ensure_default_settings

        Base.metadata.create_all(get_engine())
        with SessionLocal() as s:  # type: ignore[misc]
            ensure_default_settings(s)
            if s.query(AdminUser).count() == 0:
                s.add(AdminUser(
                    email=cfg.admin_email,
                    password_hash=hash_password(cfg.admin_password),
                    full_name="Owner", role="owner",
                ))
                log.info("bootstrapped admin %s (SQLite dev mode)", cfg.admin_email)
            s.commit()
    yield


def create_app() -> FastAPI:
    cfg = get_settings()
    app = FastAPI(
        title="Memes Pages API",
        version="1.0.0",
        description="Content discovery, management, analytics and publishing automation",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Rate limiting (per IP) ───────────────────────────────────────
    from backend.app.deps import RateLimiter, get_client_ip

    limiter = RateLimiter(cfg.api_rate_limit)

    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next):
        if request.url.path.startswith("/api/"):
            ip = get_client_ip(request)
            if not limiter.check(ip):
                return JSONResponse(
                    {"detail": "rate limit exceeded"},
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers=limiter.headers,
                )
        return await call_next(request)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            {"detail": exc.errors()[:6]}, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        from memes_shared.db.session import SessionLocal
        from memes_shared.models import ErrorLog

        try:
            with SessionLocal() as s:  # type: ignore[misc]
                s.add(ErrorLog(
                    scope="api", error_type=type(exc).__name__,
                    message=f"{request.url.path}: {exc}"[:1900],
                    severity="error",
                ))
                s.commit()
        except Exception:
            pass
        return JSONResponse({"detail": "internal server error"},
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    # ── Static media (covers, processed videos) ──────────────────────
    media_dir = cfg.media_path
    for sub in ("videos", "covers", "uploads", "tmp"):
        (media_dir / sub).mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

    # ── Routers ──────────────────────────────────────────────────────
    from backend.app.routers import (
        accounts,
        ai,
        analytics,
        audit,
        auth,
        automation,
        captions,
        content,
        covers,
        feeds,
        health,
        queue,
        reports,
        schedule,
        settings,
        sources,
        trending,
    )

    API = "/api/v1"
    app.include_router(health.router, prefix=API, tags=["health"])
    app.include_router(auth.router, prefix=f"{API}/auth", tags=["auth"])
    app.include_router(accounts.router, prefix=f"{API}/accounts", tags=["accounts"])
    app.include_router(sources.router, prefix=f"{API}/sources", tags=["sources"])
    app.include_router(feeds.router, prefix=f"{API}/feeds", tags=["feeds"])
    app.include_router(trending.router, prefix=f"{API}/trending", tags=["trending"])
    app.include_router(content.router, prefix=f"{API}/content", tags=["content"])
    app.include_router(queue.router, prefix=f"{API}/queue", tags=["queue"])
    app.include_router(schedule.router, prefix=f"{API}/schedule", tags=["schedule"])
    app.include_router(captions.router, prefix=f"{API}/captions", tags=["captions"])
    app.include_router(covers.router, prefix=f"{API}/covers", tags=["covers"])
    app.include_router(analytics.router, prefix=f"{API}/analytics", tags=["analytics"])
    app.include_router(reports.router, prefix=f"{API}/reports", tags=["reports"])
    app.include_router(settings.router, prefix=f"{API}/settings", tags=["settings"])
    app.include_router(ai.router, prefix=f"{API}/ai", tags=["ai"])
    app.include_router(automation.router, prefix=f"{API}/automation", tags=["automation"])
    app.include_router(audit.router, prefix=f"{API}/audit", tags=["audit"])
    return app


app = create_app()
