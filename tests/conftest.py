"""Pytest fixtures: in-memory-ish SQLite DB per session, ffmpeg sample video."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "shared"))
sys.path.insert(0, str(ROOT / "backend"))

# Isolated temp media dir + sqlite DB for the whole test run
_TMP = tempfile.mkdtemp(prefix="memes_test_")
os.environ["MEMES_MEDIA_DIR"] = str(Path(_TMP) / "media")
os.environ["MEMES_DATABASE_URL"] = f"sqlite:///{_TMP}/test.db"
os.environ["MEMES_SECRET_KEY"] = "test-secret-key-0123456789abcdef-memes"
os.environ["MEMES_BOT_TOKEN"] = ""

from memes_shared.db.base import Base  # noqa: E402
import memes_shared.models  # noqa: F402,E402
from memes_shared.db.session import create_engine_and_session  # noqa: E402

_engine, _Session = create_engine_and_session()
Base.metadata.create_all(_engine)


@pytest.fixture()
def db():
    """Fresh transactional session per test (tables persist, rows rolled back)."""
    conn = _engine.connect()
    tx = conn.begin()
    session = _Session(bind=conn)
    try:
        yield session
    finally:
        session.close()
        tx.rollback()
        conn.close()


@pytest.fixture(scope="session")
def sample_video() -> str | None:
    """Generate a small test mp4 with ffmpeg (skip-based tests if absent)."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    out = Path(_TMP) / "sample.mp4"
    cmd = [
        ffmpeg, "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x320:rate=15",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
        "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-pix_fmt", "yuv420p",
        str(out),
    ]
    subprocess.run(cmd, check=False, capture_output=True, timeout=120)
    return str(out) if out.exists() else None


@pytest.fixture(scope="session")
def sample_cover() -> str | None:
    from PIL import Image

    p = Path(_TMP) / "cover.png"
    Image.new("RGB", (1080, 1920), (20, 24, 40)).save(p)
    return str(p)
