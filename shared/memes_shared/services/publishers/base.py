"""Publisher abstraction — official platform APIs only.

The system never bypasses platform enforcement: publishing goes through
official APIs (Instagram Graph API, YouTube Data API) or the dry-run mode.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from memes_shared.models import DestinationAccount, PublishingJob


@dataclass
class PublishResult:
    success: bool
    external_id: str = ""
    permalink: str = ""
    raw: dict = field(default_factory=dict)
    error: str = ""
    # rate_limit | auth | transient | config | invalid
    error_type: str = ""


class Publisher(ABC):
    name: str = "base"

    @abstractmethod
    def publish(
        self,
        *,
        video_path: str,
        caption: str,
        cover_path: str,
        account: DestinationAccount,
        job: PublishingJob,
        creds: dict[str, Any],
    ) -> PublishResult: ...


def http_error_type(status_code: int, body: dict | str) -> str:
    """Classify platform API failures conservatively."""
    text = str(body).lower()
    if status_code in (401, 403):
        return "auth"
    if status_code == 429 or "rate limit" in text or "#4" in text and "application limit" in text:
        return "rate_limit"
    if 500 <= status_code < 600:
        return "transient"
    return "invalid"
