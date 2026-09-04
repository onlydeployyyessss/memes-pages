# 🤖 OpenRouter AI integration

OpenRouter is the AI provider behind Memes Pages' AI features, integrated
through a **modular provider layer** — it can be replaced by any future
provider implementing `AIProvider`.

## Setup

1. Get an API key at <https://openrouter.ai/keys>.
2. Set it **only** as an environment variable (`.env` locally, Railway
   variables/secrets in production):
   ```
   OPENROUTER_API_KEY=sk-or-v1-…
   OPENROUTER_MODEL=minimax/minimax-m3:free
   OPENROUTER_MAX_TOKENS=1000
   OPENROUTER_TIMEOUT=30
   ```
3. Restart backend + worker. Dashboard → 🤖 AI shows **🟢 Connected** and
   offers a **Test Connection** button.

### Supported models (selectable in Dashboard → 🤖 AI)

| Model | Notes |
|---|---|
| `minimax/minimax-m3:free` | **default** |
| `inclusionai/ling-3.0-flash-fin:free` | fast chat |
| `nvidia/nemotron-3-ultra-550b-a55b:free` | larger reasoning |
| `liquid/lfm-2.5-embedding-350m:free` | ⚠️ embedding model — chat calls fail (system falls back) |

Any other OpenRouter model id can be pasted into the model field.

## Where AI is used

| Feature | Where | Fallback |
|---|---|---|
| 🔥 Trend Hunter analysis | worker `trend_scan` — structured JSON `{trend_score, trend_level, confidence, category, reason, recommendation}` validated by Pydantic; optionally blended into the final score with a bounded adjustment (≤10 by default) | deterministic score (views/engagement/growth/age) |
| 📝 Captions | per-account opt-in ("AI captions" toggle) at job creation | configured default/template caption |
| #️⃣ Hashtags / categorize / language | Dashboard → Captions → AI tools + REST API | — |
| 📊 Reports | AI-written summary appended to the DB-derived report (uses **only** real analytics) | plain report |
| 🤖 Telegram assistant | "🤖 Ask AI" menu — answers from live DB context JSON | deterministic quick-stats reply |

## Cost & safety controls

- Configurable **max requests per hour / per day** (default 30 / 300) —
  enforced in code *before* any call, per service, from `ai_usage_logs`.
- `OPENROUTER_MAX_TOKENS` + `OPENROUTER_TIMEOUT` (env) + retries setting.
- Every call logged (`ai_usage_logs`: model, feature, tokens, latency,
  success, error type) — visible in Dashboard → 🤖 AI.
- **The AI never bypasses** source authorization, duplicate detection,
  publishing limits, or platform error handling. It assists; deterministic
  rules decide.
- If OpenRouter is unavailable / errors / times out / returns malformed JSON /
  hits a usage limit → features return empty and automation continues.

## Security of the API key

- Read **only** from the `OPENROUTER_API_KEY` environment variable.
- Never committed (`.env` is git-ignored; `.env.example` has a blank placeholder).
- Never returned by API endpoints (`/ai/status` only reports
  `key_configured: true/false`), never logged, never sent to the frontend.

## Testing

`pytest tests/test_ai.py` covers: JSON extraction (plain/fenced/garbage),
Pydantic validation & clamping, provider error classification (auth /
rate-limit / timeout), usage recording, budget blocking, malformed-output
fallback, provider-exception survival, end-to-end trend-scan fallback, and API
key non-exposure.
