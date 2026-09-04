"""Pydantic validation of AI responses — malformed output never crashes us."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _clamp(value: float, lo: float, hi: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        try:
            value = float(str(value).strip())
        except (TypeError, ValueError):
            raise ValueError(f"not a number: {value!r}")
    return max(lo, min(hi, float(value)))


class TrendAnalysis(BaseModel):
    """Structured Trend Hunter AI response."""

    model_config = ConfigDict(extra="ignore")

    trend_score: float = 0
    trend_level: str = "unknown"       # e.g. low | rising | hot | viral
    confidence: float = 0.5
    category: str = "memes"
    reason: str = ""
    recommendation: str = "queue"      # queue | skip | watch

    @field_validator("trend_score", mode="before")
    @classmethod
    def _score(cls, v):
        return _clamp(v, 0, 100)

    @field_validator("confidence", mode="before")
    @classmethod
    def _conf(cls, v):
        return _clamp(v, 0, 1)

    @field_validator("trend_level", "category", "reason", "recommendation", mode="before")
    @classmethod
    def _strings(cls, v):
        return str(v or "")[:300]


def parse_trend_analysis(raw: dict) -> TrendAnalysis | None:
    """Validate a parsed AI dict; returns None on any schema violation."""
    if not isinstance(raw, dict):
        return None
    try:
        return TrendAnalysis.model_validate(raw)
    except Exception:  # noqa: BLE001 — any malformed shape → fallback
        return None
