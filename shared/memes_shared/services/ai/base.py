"""AIProvider interface — swap providers without touching feature code."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class AIResponse:
    """Normalized provider response."""

    ok: bool
    content: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    error: str = ""
    # auth | rate_limit | timeout | usage_limit | invalid | transient
    error_type: str = ""


class AIProvider(ABC):
    """Contract: one-shot chat completion against an AI backend."""

    name: str = "base"

    @abstractmethod
    def chat(
        self,
        *,
        system: str,
        user: str,
        max_tokens: int = 1000,
        temperature: float = 0.4,
        json_mode: bool = False,
    ) -> AIResponse: ...

    @abstractmethod
    def test_connection(self) -> AIResponse: ...
