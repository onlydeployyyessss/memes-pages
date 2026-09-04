# 🏗 Architecture

## System overview

```
                        ┌──────────────────────────────────────────────┐
                        │                PostgreSQL (26 tables)        │
                        │  state of everything: content, jobs, metrics │
                        └───────▲──────────────▲──────────────▲────────┘
                                │              │              │
  ┌──────────────┐    ┌────────┴─────┐  ┌─────┴──────┐  ┌────┴────────┐
  │  Telegram    │    │   Backend    │  │   Worker   │  │  Frontend   │
  │  Bot         │───▶│  FastAPI     │◀─│  Memes     │◀─│  Next.js    │
  │  (aiogram 3) │    │  REST API    │  │  Pages     │  │  Dashboard  │
  └──────────────┘    └──────────────┘  │  Agent     │  └─────────────┘
                                        │ (APScheduler)            
                                        └─────┬──────┬───────┬───────
                                              │      │       │
                                    discovery │ pipeline │ publishing
                                              ▼      ▼       ▼
                                    RSS/feeds  ffmpeg   platform APIs
                                    Agent-Reach phash   (official only)
```

All four services are **stateless processes** sharing one PostgreSQL database —
any of them can restart at any time without losing work. Redis is optional
(rate limiting / caching); the API falls back to in-memory buckets.

## The automation loop (Memes Pages Agent)

The worker runs the following jobs on intervals (see `worker/main.py`):

| Job | Interval | What it does |
|---|---|---|
| `discovery` | 5 min | Every enabled & due source → its provider → upsert `discovered_content` |
| `trend_scan` | 3 min | Score unscored items (Trend Hunter) → persist `trend_scores` + `trend_history` → evaluate **rule engine** → approved items enter the pipeline |
| `pipeline` | 2 min | Retry interrupted `processing` items |
| `schedule` | 2 min | Assign `publish_at` + batches to unassigned queued jobs |
| `publish` | 45 s | Dispatch due jobs through publishers (dry-run or official APIs) |
| `metrics` | 6 h | Pull account metrics via official APIs (or simulated in dry-run) |
| `reports` | daily 21:05 | Daily/weekly/monthly reports → Telegram |
| `cleanup` | daily 04:30 | Remove temp media |

Admins can hit **Run Now** (dashboard or bot) — the worker executes a full
cycle immediately. Automation gate: nothing auto-runs unless the global
automation state is **enabled** (except manual force-dispatches).

## Trend Hunter — scoring

`services/trend_engine.py` computes a 0–100 score:

```
score = 100 × Σ weightᵢ × normalized_signalᵢ
signals: views, likes, comments, shares, engagement_rate,
         growth_rate (explicit or derived from trend_history),
         velocity (growth × recency blend), freshness
         (exponential decay with configurable half-life), source_history
```

All weights and normalizers live in the `trend` settings key and are editable
from Dashboard → Settings. The engine returns a full per-signal breakdown
stored with each score and surfaced in the UI/bot.

## Rule engine (no manual approval)

`services/rule_engine.py` evaluates the configured thresholds
(min trend score, min engagement, max age, category allow-list, keyword
allow/block lists, daily cap, authorized-source requirement, video-only).
Failure of **soft checks** (score/engagement/age/daily cap) keeps the item
`detected` for future re-scoring; **hard checks** (authorization, category,
keywords, media type) mark it `skipped`. Approved items proceed automatically —
there is no approval step anywhere in the codebase.

## Discovery Provider Interface

```python
class DiscoveryProvider(ABC):
    name: str
    def supports(self, source_type: str) -> bool: ...
    def fetch(self, source, feed=None) -> tuple[list[DiscoveryItem], dict]: ...
```

Registered providers (`services/discovery/`):

1. **RSSProvider** — RSS/Atom via feedparser (etags, media enclosures,
   metric extensions). Primary, fully supported.
2. **AuthorizedFeedProvider** — partner JSON feeds (`{items:[…]}`).
3. **AgentReachProvider** — experimental; probes `agent-reach doctor --json`
   and executes a configured command template (see
   [AGENT_REACH_EVALUATION.md](AGENT_REACH_EVALUATION.md)). Disabled unless
   explicitly enabled.

Provider errors are recorded per-source (`success_count`/`error_count`,
`automation_logs`) and never halt the loop. Future providers only need to
implement the interface and register in `PROVIDERS`.

## Content pipeline

```
detected → validate source (enabled + authorized) → media URL check →
pre-download dedup (source URL / external id) → download (≤500 MB cap) →
ffprobe validation (duration/streams) → SHA-256 + perceptual frame hashes →
post-download dedup (exact + perceptual ≤9% frame distance) →
ffmpeg normalize (h264/aac, ≤1920px, faststart) → auto cover frame →
videos + video_hashes rows → multi-account publishing jobs
```

## Batch scheduler

Pure, testable math (`services/scheduler.py::plan_publish_times`):

- batch size, initial delay, fixed or random (min–max) gaps
- rest period between batches (e.g. 5.5 h)
- posting window (local hours) + quiet hours, daily caps, timezone

Jobs are grouped into `publishing_batches`; the scheduler never plans a
batch while the previous one is resting.

## Publishing & safety

Publishers registry (`services/publishers/`):

| Platform | Implementation |
|---|---|
| `dry_run` | end-to-end simulation (default global mode) |
| `instagram` | official **Instagram Graph API** (container → publish), needs public media URL |
| `youtube` | official **YouTube Data API v3** resumable upload (Shorts) |
| `tiktok` / `custom` | dry-run until connected properly |

Failure classification: `rate_limit` → job rescheduled after cooldown,
account paused, **dispatch loop stops**, admin alert. `auth` → account
integration marked `token_error`, admin alert. `transient` → exponential
backoff (base × 2^attempt). `config`/`invalid` → failed with clear message.

## Security model

- **JWT** (HS256, 12 h) for dashboard sessions; bcrypt password hashing
- **RBAC**: owner / admin / viewer (`require_role` dependency)
- **Credential encryption**: destination-account tokens encrypted with
  Fernet (key derived from `MEMES_CREDENTIAL_ENCRYPTION_KEY`), never returned
  by the API
- **Rate limiting** per IP on `/api/*`
- **Audit logs** for every admin action; error logs for every failure scope
- Secrets only via environment variables; `.env` is git-ignored
