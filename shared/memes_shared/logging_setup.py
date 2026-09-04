"""Structured logging setup shared by all services."""
from __future__ import annotations

import logging
import sys

from memes_shared.config import get_settings

_FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def setup_logging(level: str | None = None) -> None:
    cfg = get_settings()
    lvl = getattr(logging, (level or cfg.log_level).upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMAT, _DATEFMT))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(lvl)
    for noisy in ("httpx", "httpcore", "apscheduler.executors.default"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
