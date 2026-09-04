"""Engine / session management (sync SQLAlchemy, threadpool-friendly)."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from memes_shared.config import get_settings

_engine = None
_SessionFactory: sessionmaker | None = None


def create_engine_and_session(database_url: str | None = None):
    """Create (engine, sessionmaker) for the given or configured URL."""
    from memes_shared.db.base import Base  # noqa: F401  (register metadata)

    url = database_url or get_settings().effective_database_url
    kwargs: dict = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    else:
        kwargs.update({"pool_size": 10, "max_overflow": 20, "pool_recycle": 1800})
    eng = create_engine(url, **kwargs)
    sm = sessionmaker(bind=eng, expire_on_commit=False, autoflush=False)
    return eng, sm


def get_engine():
    global _engine, _SessionFactory
    if _SessionFactory is None:
        _engine, _SessionFactory = create_engine_and_session()
    return _engine


def SessionLocal() -> Session:
    get_engine()
    return _SessionFactory()


@contextmanager
def get_session() -> Iterator[Session]:
    """Context-managed session; commits on success, rolls back on error."""
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()
