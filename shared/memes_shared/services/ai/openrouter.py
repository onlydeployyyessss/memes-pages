"""OpenRouter provider — https://openrouter.ai (OpenAI-compatible API).

The API key NEVER leaves the server: it is read from the
OPENROUTER_API_KEY environment variable and only sent to OpenRouter.
"""
from __future__ import annotations

import time

import httpx

from memes_shared.logging_setup import get_logger
from memes_shared.services.ai.base import AIProvider, AIResponse

log = get_logger("memes.ai.openrouter")

API_BASE = "https://openrouter.ai/api/v1"


class OpenRouterProvider(AIProvider):
    name = "openrouter"

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout: float = 30.0,
        max_tokens: int = 1000,
    ):
        self.api_key = api_key
        self.model = model or "minimax/minimax-m3:free"
        self.timeout = float(timeout or 30)
        self.max_tokens = int(max_tokens or 1000)

    # ── Core call ────────────────────────────────────────────────────
    def chat(self, *, system: str, user: str, max_tokens: int | None = None,
             temperature: float = 0.4, json_mode: bool = False) -> AIResponse:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": int(max_tokens or self.max_tokens),
            "temperature": temperature,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://memes-pages.app",
            "X-Title": "Memes Pages",
        }
        started = time.monotonic()
        try:
            resp = httpx.post(f"{API_BASE}/chat/completions", json=payload,
                              headers=headers, timeout=self.timeout)
        except httpx.TimeoutException:
            return AIResponse(ok=False, error="request timed out", error_type="timeout",
                              latency_ms=int((time.monotonic() - started) * 1000))
        except httpx.HTTPError as e:
            return AIResponse(ok=False, error=str(e)[:300], error_type="transient",
                              latency_ms=int((time.monotonic() - started) * 1000))
        latency = int((time.monotonic() - started) * 1000)

        if resp.status_code >= 400:
            # never include the key in errors — body only, scrubbed defensively
            body = resp.text[:300].replace(self.api_key, "***")
            if resp.status_code in (401, 403):
                etype = "auth"
            elif resp.status_code == 429:
                etype = "rate_limit"
            elif resp.status_code >= 500:
                etype = "transient"
            else:
                etype = "invalid"
            return AIResponse(ok=False, error=f"HTTP {resp.status_code}: {body}",
                              error_type=etype, model=self.model, latency_ms=latency)

        try:
            data = resp.json()
        except ValueError:
            return AIResponse(ok=False, error="non-JSON response body",
                              error_type="invalid", model=self.model, latency_ms=latency)
        content = ""
        choices = data.get("choices") or []
        if choices:
            content = ((choices[0].get("message") or {}).get("content")) or ""
        usage = data.get("usage") or {}
        return AIResponse(
            ok=bool(content.strip()),
            content=content,
            model=data.get("model", self.model),
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
            latency_ms=latency,
            error="" if content.strip() else "empty response",
            error_type="" if content.strip() else "invalid",
        )

    def test_connection(self) -> AIResponse:
        return self.chat(
            system="You are a connection test. Reply with exactly: OK",
            user="ping",
            max_tokens=10,
            temperature=0.0,
        )
