"""Central AI service — every feature talks to AI through this module.

Guarantees:
  * No AI failure can crash automation (all paths return None on error)
  * Usage budgets (per hour / per day) are enforced before any call
  * Every call is logged to ai_usage_logs (tokens, latency, success, error)
  * Without OPENROUTER_API_KEY everything degrades to deterministic behavior
"""
from __future__ import annotations

import json
import re
import time

from sqlalchemy.orm import Session

from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger
from memes_shared.models import AIUsageLog
from memes_shared.services.ai.openrouter import OpenRouterProvider
from memes_shared.services.ai.prompts import (
    ASSISTANT_SYSTEM,
    CAPTION_SYSTEM,
    CATEGORY_SYSTEM,
    HASHTAG_SYSTEM,
    LANGUAGE_SYSTEM,
    REPORT_SYSTEM,
    TREND_SYSTEM,
    assistant_user_prompt,
    caption_user_prompt,
    category_user_prompt,
    hashtag_user_prompt,
    report_user_prompt,
    trend_user_prompt,
)
from memes_shared.services.ai.schemas import TrendAnalysis, parse_trend_analysis
from memes_shared.services.settings import get_setting
from memes_shared.utils.timeutil import utcnow

log = get_logger("memes.ai")

_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def extract_json(text: str) -> dict | None:
    """Robustly pull the first JSON object out of an LLM answer."""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*|```\s*$", "", cleaned, flags=re.MULTILINE).strip()
    candidates = [cleaned]
    match = _JSON_RE.search(cleaned)
    if match:
        candidates.insert(0, match.group(0))
    for cand in candidates:
        try:
            data = json.loads(cand)
            if isinstance(data, dict):
                return data
        except json.JSONDecodeError:
            continue
    return None


class AIService:
    """Provider-agnostic facade used by Trend Hunter, captions, reports, bot."""

    def __init__(self, session: Session):
        self.session = session
        self.cfg = get_setting(session, "ai")
        cfg_settings = get_settings()
        self.env_model = cfg_settings.openrouter_model
        key = cfg_settings.openrouter_api_key
        self.provider = None
        if key and self.cfg.get("enabled", True):
            model = (self.cfg.get("model") or "").strip() or self.env_model
            self.provider = OpenRouterProvider(
                api_key=key,
                model=model,
                timeout=cfg_settings.openrouter_timeout,
                max_tokens=cfg_settings.openrouter_max_tokens,
            )

    # ── State ────────────────────────────────────────────────────────
    @property
    def configured(self) -> bool:
        return self.provider is not None and bool(self.cfg.get("enabled", True))

    def usage_counts(self) -> dict:
        """Requests today / this hour + tokens today (from usage log)."""
        now = utcnow()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        hour_start = now.replace(minute=0, second=0, microsecond=0)
        q = self.session.query(AIUsageLog)
        today = q.filter(AIUsageLog.created_at >= day_start).count()
        hour = q.filter(AIUsageLog.created_at >= hour_start).count()
        tokens = 0
        for row in q.filter(AIUsageLog.created_at >= day_start):
            tokens += row.prompt_tokens + row.completion_tokens
        return {"today": today, "hour": hour, "tokens_today": tokens}

    def _within_budget(self) -> tuple[bool, str]:
        limits = self.usage_counts()
        max_day = int(self.cfg.get("max_requests_per_day") or 0)
        max_hour = int(self.cfg.get("max_requests_per_hour") or 0)
        if max_day and limits["today"] >= max_day:
            return False, f"daily AI request limit reached ({limits['today']}/{max_day})"
        if max_hour and limits["hour"] >= max_hour:
            return False, f"hourly AI request limit reached ({limits['hour']}/{max_hour})"
        return True, ""

    # ── Core call with retry + logging ───────────────────────────────
    def _chat(self, feature: str, *, system: str, user: str,
              max_tokens: int | None = None, temperature: float = 0.4):
        if not self.configured:
            return None
        ok_budget, reason = self._within_budget()
        if not ok_budget:
            log.info("AI call skipped (%s): %s", feature, reason)
            return None

        retries = max(0, int(self.cfg.get("retries", 1)))
        response = None
        for attempt in range(retries + 1):
            try:
                response = self.provider.chat(system=system, user=user,
                                              max_tokens=max_tokens,
                                              temperature=temperature)
            except Exception as e:
                from memes_shared.services.ai.base import AIResponse

                response = AIResponse(ok=False, error=f"provider exception: {e}"[:400],
                                      error_type="transient")
            if response.ok or response.error_type not in ("transient", "rate_limit", "timeout"):
                break
            time.sleep(0.8 * (attempt + 1))

        self.session.add(AIUsageLog(
            provider=self.provider.name,
            model=response.model or self.provider.model,
            feature=feature,
            success=response.ok,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=response.latency_ms,
            error_type=response.error_type or "",
            error=(response.error or "")[:500],
        ))
        self.session.flush()
        if not response.ok:
            log.warning("AI %s failed (%s): %s", feature, response.error_type,
                        response.error[:200])
        return response if response.ok else None

    def _chat_json(self, feature: str, *, system: str, user: str,
                   max_tokens: int | None = None, temperature: float = 0.2) -> dict | None:
        response = self._chat(feature, system=system, user=user,
                              max_tokens=max_tokens, temperature=temperature)
        if response is None:
            return None
        return extract_json(response.content)

    # ── Features ─────────────────────────────────────────────────────
    def analyze_trend(self, meta: dict) -> TrendAnalysis | None:
        """Structured trend analysis. Returns None on ANY failure → caller
        falls back to the deterministic Trend Hunter score."""
        data = self._chat_json("trend_analysis", system=TREND_SYSTEM,
                               user=trend_user_prompt(meta), max_tokens=400)
        if data is None:
            return None
        return parse_trend_analysis(data)

    def generate_captions(self, *, title: str, description: str = "",
                          category: str = "memes", tone: str = "fun, casual",
                          count: int = 3, platform: str = "instagram") -> list[str]:
        data = self._chat_json("captions", system=CAPTION_SYSTEM,
                               user=caption_user_prompt(title=title,
                                                        description=description,
                                                        category=category, tone=tone,
                                                        count=count, platform=platform),
                               max_tokens=700)
        captions = (data or {}).get("captions")
        if isinstance(captions, list):
            return [str(c).strip()[:900] for c in captions if str(c).strip()][:count]
        return []

    def generate_hashtags(self, *, title: str, category: str = "memes",
                          count: int = 12) -> list[str]:
        data = self._chat_json("hashtags", system=HASHTAG_SYSTEM,
                               user=hashtag_user_prompt(title=title,
                                                        category=category, count=count),
                               max_tokens=200)
        tags = (data or {}).get("hashtags")
        if isinstance(tags, list):
            out = []
            for t in tags:
                t = str(t).strip().lstrip("#").lower()
                if t and t not in out:
                    out.append(t)
            return out[:count]
        return []

    def categorize(self, *, title: str, description: str = "") -> str:
        data = self._chat_json("categorize", system=CATEGORY_SYSTEM,
                               user=category_user_prompt(title, description),
                               max_tokens=60)
        cat = (data or {}).get("category")
        return str(cat).strip().lower()[:40] if cat else ""

    def detect_language(self, text: str) -> str:
        data = self._chat_json("language", system=LANGUAGE_SYSTEM,
                               user=text[:800], max_tokens=30)
        lang = (data or {}).get("language")
        return str(lang).strip().lower()[:8] if lang else ""

    def summarize_report(self, report_text: str, payload: dict) -> str:
        response = self._chat("report_summary", system=REPORT_SYSTEM,
                              user=report_user_prompt(report_text, payload),
                              max_tokens=350, temperature=0.5)
        return response.content.strip()[:1500] if response else ""

    def assistant_answer(self, question: str, context_json: str) -> str:
        response = self._chat("assistant", system=ASSISTANT_SYSTEM,
                              user=assistant_user_prompt(question, context_json),
                              max_tokens=500, temperature=0.4)
        return response.content.strip()[:3500] if response else ""

    def test_connection(self) -> dict:
        """Minimal authenticated request — never exposes the key."""
        if not self.configured:
            return {"ok": False, "configured": False,
                    "message": "OPENROUTER_API_KEY is not set (or AI disabled) — "
                               "add it as an environment variable and restart."}
        response = self.provider.test_connection()
        self.session.add(AIUsageLog(
            provider=self.provider.name, model=response.model or self.provider.model,
            feature="test", success=response.ok,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=response.latency_ms,
            error_type=response.error_type or "",
            error=(response.error or "")[:500],
        ))
        self.session.flush()
        return {
            "ok": response.ok,
            "configured": True,
            "model": response.model or self.provider.model,
            "latency_ms": response.latency_ms,
            "message": "🟢 Connected — authentication works" if response.ok
            else f"🔴 {response.error_type or 'error'}: {response.error[:200]}",
        }


def get_ai(session: Session) -> AIService:
    return AIService(session)
