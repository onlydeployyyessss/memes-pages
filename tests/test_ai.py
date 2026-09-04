"""OpenRouter AI layer tests: parsing, fallback, budgets, key security."""
import json

import pytest

from memes_shared.models import AIUsageLog
from memes_shared.services.ai import (
    AIResponse,
    OpenRouterProvider,
    extract_json,
    get_ai,
    parse_trend_analysis,
)


# ── Response parsing ─────────────────────────────────────────────────
def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_code_fence_and_prose():
    text = 'Sure! Here you go:\n```json\n{"trend_score": 91, "reason": "hot"}\n```\nDone.'
    assert extract_json(text)["trend_score"] == 91


def test_extract_json_garbage():
    assert extract_json("no json at all") is None
    assert extract_json("") is None


def test_trend_analysis_clamps_ranges():
    a = parse_trend_analysis({"trend_score": 250, "confidence": 5, "reason": "hot"})
    assert a is not None
    assert a.trend_score == 100
    assert a.confidence == 1


def test_trend_analysis_rejects_garbage_score():
    # non-numeric score → validation failure → None (deterministic fallback)
    assert parse_trend_analysis({"trend_score": "very hot"}) is None
    assert parse_trend_analysis(["not", "a", "dict"]) is None
    assert parse_trend_analysis(None) is None


# ── Provider error classification ────────────────────────────────────
class _FakeResp:
    def __init__(self, status_code=200, body=None, text=""):
        self.status_code = status_code
        self._body = body or {}
        self.text = text

    def json(self):
        return self._body


def test_provider_classifies_auth_errors(monkeypatch):
    import memes_shared.services.ai.openrouter as orp

    provider = OpenRouterProvider(api_key="sk-test", model="m")
    monkeypatch.setattr(orp.httpx, "post",
                        lambda *a, **k: _FakeResp(401, {"error": "bad key"}, "bad key"))
    r = provider.chat(system="s", user="u")
    assert not r.ok and r.error_type == "auth"
    assert "sk-test" not in r.error  # key never leaks into errors


def test_provider_classifies_rate_limit(monkeypatch):
    import memes_shared.services.ai.openrouter as orp

    provider = OpenRouterProvider(api_key="sk-test", model="m")
    monkeypatch.setattr(orp.httpx, "post",
                        lambda *a, **k: _FakeResp(429, {}, "rate limited"))
    r = provider.chat(system="s", user="u")
    assert r.error_type == "rate_limit"


def test_provider_parses_content_and_usage(monkeypatch):
    import memes_shared.services.ai.openrouter as orp

    provider = OpenRouterProvider(api_key="sk-test", model="m")
    body = {"choices": [{"message": {"content": "OK"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            "model": "m"}
    monkeypatch.setattr(orp.httpx, "post", lambda *a, **k: _FakeResp(200, body))
    r = provider.chat(system="s", user="u")
    assert r.ok and r.content == "OK" and r.prompt_tokens == 10


def test_provider_timeout(monkeypatch):
    import httpx

    import memes_shared.services.ai.openrouter as orp

    provider = OpenRouterProvider(api_key="sk-test", model="m", timeout=1)
    def _raise(*a, **k):
        raise httpx.TimeoutException("too slow")
    monkeypatch.setattr(orp.httpx, "post", _raise)
    r = provider.chat(system="s", user="u")
    assert not r.ok and r.error_type == "timeout"


# ── Service-level behaviour ──────────────────────────────────────────
def test_service_not_configured_without_key(db):
    ai = get_ai(db)
    assert not ai.configured
    assert ai.analyze_trend({"title": "x"}) is None          # instant fallback
    assert ai.generate_captions(title="x") == []
    result = ai.test_connection()
    assert result["ok"] is False and result["configured"] is False


def test_service_success_records_usage(db, monkeypatch):
    ai = get_ai(db)
    assert not ai.configured  # no key in test env → monkeypatch provider in

    class FakeProvider:
        name = "openrouter"
        model = "minimax/minimax-m3:free"

        def chat(self, **kw):
            return AIResponse(
                ok=True,
                content=json.dumps({
                    "trend_score": 93, "trend_level": "viral",
                    "confidence": 0.9, "category": "memes",
                    "reason": "strong velocity", "recommendation": "queue",
                }),
                model="minimax/minimax-m3:free",
                prompt_tokens=120, completion_tokens=40, latency_ms=250,
            )

    ai.provider = FakeProvider()
    analysis = ai.analyze_trend({"title": "viral cat"})
    assert analysis is not None
    assert analysis.trend_score == 93
    assert analysis.recommendation == "queue"
    row = db.query(AIUsageLog).filter_by(feature="trend_analysis").first()
    assert row is not None and row.success
    assert row.prompt_tokens == 120


def test_usage_budget_blocks_calls(db, monkeypatch):
    from memes_shared.services.settings import set_setting

    set_setting(db, "ai", {"max_requests_per_day": 1})
    db.add(AIUsageLog(provider="openrouter", model="m", feature="test",
                      success=True))
    db.flush()

    calls = {"n": 0}

    class FakeProvider:
        name = "openrouter"
        model = "m"

        def chat(self, **kw):
            calls["n"] += 1
            return AIResponse(ok=True, content="{}")

    ai = get_ai(db)
    ai.provider = FakeProvider()
    assert ai.analyze_trend({"title": "x"}) is None  # budget exhausted
    assert calls["n"] == 0                           # provider never called


def test_malformed_ai_json_falls_back(db):
    class BrokenProvider:
        name = "openrouter"
        model = "m"

        def chat(self, **kw):
            return AIResponse(ok=True, content="not json at all", model="m")

    ai = get_ai(db)
    ai.provider = BrokenProvider()
    assert ai.analyze_trend({"title": "x"}) is None
    row = db.query(AIUsageLog).filter_by(feature="trend_analysis").first()
    assert row is not None and row.success  # the call itself succeeded


def test_provider_exception_never_crashes(db):
    class ExplodingProvider:
        name = "openrouter"
        model = "m"

        def chat(self, **kw):
            raise RuntimeError("boom")

    ai = get_ai(db)
    ai.provider = ExplodingProvider()
    try:
        result = ai.analyze_trend({"title": "x"})
        assert result is None
    except RuntimeError:
        pytest.fail("AI provider exception crashed the service")


# ── Deterministic trend scan continues when AI fails ─────────────────
def test_trend_scan_survives_ai_failure(db, monkeypatch):
    from datetime import timedelta

    from memes_shared.models import ContentSource, DiscoveredContent, TrendScore
    from memes_shared.services.trend_scan import run_trend_scan

    src = ContentSource(name="S", source_type="rss", authorization="authorized",
                        enabled=True, success_count=5)
    db.add(src)
    db.flush()
    from memes_shared.utils.timeutil import utcnow

    content = DiscoveredContent(
        source_id=src.id, title="Massive viral hit", url="https://s/v1",
        external_id="v1", media_type="video", category="memes",
        published_at=utcnow() - timedelta(hours=1),
        discovered_at=utcnow(),
        raw_metrics={"views": 900_000, "likes": 120_000, "comments": 9_000,
                     "shares": 30_000, "growth_rate_percent_per_hour": 400},
    )
    db.add(content)
    db.flush()

    class BrokenProvider:
        name = "openrouter"
        model = "m"

        def chat(self, **kw):
            raise RuntimeError("openrouter down")

    import memes_shared.services.ai.service as ai_service

    monkeypatch.setattr(ai_service.OpenRouterProvider, "chat",
                        lambda self, **kw: (_ for _ in ()).throw(RuntimeError("down")))
    # give the service a fake key so it constructs a provider
    import memes_shared.config as cfg_mod

    monkeypatch.setattr(cfg_mod.get_settings(), "openrouter_api_key", "sk-test", raising=False)

    result = run_trend_scan(db)
    assert result["scored"] >= 1
    db.flush()  # pending inserts become visible to queries
    ts = db.query(TrendScore).filter_by(content_id=content.id).first()
    assert ts is not None
    assert ts.score > 0                      # deterministic score exists
    assert "ai" not in (ts.signals or {})    # AI data absent → fallback worked
