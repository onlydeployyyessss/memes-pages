# 🤖 Memes Pages

**Production-ready content discovery, management, analytics and publishing automation platform.**

Controlled through a **Telegram Bot** and a **Web Admin Dashboard**. The internal
automation system is the **Memes Pages Agent**; the trend-discovery subsystem is
**Trend Hunter**.

```
Discover trending content → Analyze → Trend score → Automatic rules →
Authorization check → Obtain media → Duplicate check → Process video →
Caption + Reel cover → Publishing queue → Batch schedule → Publish →
Track performance → Reports
```

> ⚖️ **Compliance by design** — automation runs *only* for sources explicitly
> marked **Authorized**; publishing uses **official platform APIs** (Instagram
> Graph API, YouTube Data API) or a safe **dry-run** mode. Nothing here bypasses
> platform enforcement, rate limits, or terms of service.

---

## ✨ Feature highlights

| Area | What you get |
|---|---|
| 📡 **Discovery** | Pluggable **Discovery Provider Interface**: `RSSProvider` (full RSS/Atom), `AuthorizedFeedProvider` (partner JSON feeds), `AgentReachProvider` (optional, experimental) |
| 🔥 **Trend Hunter** | Configurable 0–100 trend score from views, likes, comments, shares, engagement rate, growth rate, velocity, content age & source history — with per-signal breakdown |
| ⚙️ **Rule engine** | Fully configurable auto-approval (min score, min engagement, max age, categories, keywords, daily caps, authorized-source requirement). **No manual approval step.** |
| 🔐 **Authorized sources** | Every source carries `authorized / not_authorized / disabled`; automation processes authorized sources only |
| 🎬 **Content pipeline** | Validate → SHA-256 + perceptual-hash duplicate detection → ffmpeg normalize (h264/aac/faststart) → auto cover extraction → metadata → queue |
| 📱 **Multi-account** | Unlimited destination accounts with independent captions, hashtags, covers, schedules, delays, limits and analytics |
| 📝 **Captions** | Default / per-account / weighted-random templates with `{title}`, `{hashtags}`, `{author}`… placeholders |
| 🖼 **Reel covers** | Upload, default + per-account assignment, used automatically per destination |
| 📥 **Queue & batch scheduler** | Batches with initial delay, random/fixed gaps, rest periods, posting windows, quiet hours, daily caps, timezone-aware |
| 🚨 **Scheduler safety** | Stops on rate-limit (account cooldown + admin alert), stops on auth errors, exponential backoff for transient failures, respects official limits |
| 📈 **Analytics** | Followers, views, engagement, posts; Recharts dashboards; account comparison; trending-content performance |
| 📄 **Reports** | Daily / weekly / monthly / network / account reports — pushed to Telegram automatically |
| 🔔 **Notifications** | Publish success/failure, high trend scores, milestones, automation errors, daily report |
| 🛡 **Security** | JWT auth, bcrypt password hashing, role-based access (owner/admin/viewer), AES (Fernet) credential encryption at rest, rate limiting, audit logs |

## 🧱 Tech stack

- **Backend** Python 3.12 · FastAPI · SQLAlchemy 2 · Alembic
- **Bot** Python · aiogram 3
- **Worker** APScheduler + custom Python workers
- **Database** PostgreSQL (+ Redis optional)
- **Video** FFmpeg
- **Frontend** Next.js 14 · React 18 · Tailwind CSS · Recharts
- **Deploy** Docker · Docker Compose · Railway

## 📁 Project structure

```
memes-pages/
├── backend/          # FastAPI REST API (app/)
├── telegram-bot/     # aiogram bot (telegram_bot/)
├── worker/           # automation loop (APScheduler jobs)
├── shared/           # domain models + services (memes_shared/)
│   └── services/     # trend engine, rules, pipeline, scheduler,
│                     # publishers, discovery providers, reports…
├── frontend/         # Next.js dashboard
├── scripts/          # seed_admin, demo data
├── docker/           # Dockerfiles
├── docs/             # architecture, deployment, bot, agent-reach
├── tests/            # pytest suite (46 tests)
├── docker-compose.yml
├── .env.example
└── README.md
```

## 🚀 Quick start (local)

```bash
# 1. clone & configure
git clone <your-repo-url> memes-pages && cd memes-pages
cp .env.example .env            # fill values (see below)

# 2. infrastructure
docker compose up -d postgres redis

# 3. python deps
pip install -r requirements.txt
pip install -e ./shared --no-deps
sudo apt install ffmpeg          # video processing

# 4. database + admin
export MEMES_DATABASE_URL=postgresql://memes:memes@localhost:5432/memes_pages
alembic -c shared/alembic.ini upgrade head
python -m scripts.seed_admin              # creates admin from .env
python -m scripts.seed_admin --demo       # optional demo data

# 5. run everything (4 processes)
uvicorn app.main:app --app-dir backend --port 8000   # API
python -m worker.main                                # automation agent
python -m telegram_bot.bot                           # Telegram bot
cd frontend && npm install && npm run dev            # dashboard :3000
```

Open **http://localhost:3000** → sign in. API docs at
**http://localhost:8000/api/docs**.

### Or everything at once

```bash
docker compose up --build
```

## ⚙️ Required environment variables

See [`.env.example`](.env.example) for the full annotated list. The essentials:

| Variable | Purpose |
|---|---|
| `MEMES_SECRET_KEY` | JWT signing — **change it** |
| `MEMES_DATABASE_URL` | PostgreSQL DSN |
| `MEMES_ADMIN_EMAIL` / `MEMES_ADMIN_PASSWORD` | bootstrap dashboard admin |
| `MEMES_BOT_TOKEN` | from [@BotFather](https://t.me/BotFather) |
| `MEMES_ADMIN_TELEGRAM_IDS` | comma-separated Telegram user IDs allowed to control the bot |
| `MEMES_MEDIA_DIR` | media storage |
| `MEMES_PUBLIC_MEDIA_BASE_URL` | public URL serving `/media` (required for Instagram API publishing) |
| `MEMES_CREDENTIAL_ENCRYPTION_KEY` | key for account credentials at rest |
| `MEMES_AGENT_REACH_ENABLED` | opt-in for the experimental Agent-Reach provider |

## 🤖 Telegram bot

1. Create a bot with **@BotFather** → copy the token into `MEMES_BOT_TOKEN`.
2. Send `/id` to your bot (or @userinfobot) and put your ID in
   `MEMES_ADMIN_TELEGRAM_IDS`.
3. `/start` → main menu:

```
🤖 MEMES PAGES
📊 Dashboard   📱 Accounts   🔥 Trending    🎬 Content
📥 Queue       📅 Schedule   📝 Captions    🖼 Covers
📈 Analytics   📄 Reports    ⚙️ Settings    🟢 Automation
```

Upload a video directly to the bot → add a caption → pick destination
accounts → **publish now** or **schedule**.

Full guide: [`docs/TELEGRAM_BOT.md`](docs/TELEGRAM_BOT.md).

## 🐘 Deployment (Railway)

The repo is Railway-ready: 5 services from one repository
(PostgreSQL, Redis, backend, worker, telegram-bot, frontend).
Step-by-step guide with per-service settings:
[`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md).

## 📡 Discovery providers & Agent-Reach

RSS works out of the box. [Agent-Reach](https://github.com/Panniantong/Agent-Reach)
was evaluated and integrated as an **optional, non-blocking** provider behind the
same `DiscoveryProvider` interface — the full honest evaluation and integration
contract is in [`docs/AGENT_REACH_EVALUATION.md`](docs/AGENT_REACH_EVALUATION.md).
The system never depends on it.

## 🧪 Tests

```bash
python -m pytest tests -q     # 46 tests: trend engine, rules, scheduler math,
                              # dedup, pipeline e2e (real ffmpeg), publishing
                              # safety, API integration, security
```

## 🗄 Database

26 tables — users, admin_users, destination_accounts, account_settings,
account_metrics, content_sources, rss_feeds, discovered_content, videos,
video_hashes, trend_scores, trend_history, captions, caption_templates,
reel_covers, publishing_jobs, publishing_batches, publishing_history,
schedules, analytics, daily_metrics, reports, automation_logs, error_logs,
audit_logs, app_settings. Migrations: `alembic -c shared/alembic.ini upgrade head`.

## 📚 Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — full system architecture
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — GitHub + Railway deployment
- [`docs/TELEGRAM_BOT.md`](docs/TELEGRAM_BOT.md) — bot setup & commands
- [`docs/AGENT_REACH_EVALUATION.md`](docs/AGENT_REACH_EVALUATION.md) — provider evaluation

## ⚖️ Acceptable-use summary

This platform is built for **authorized content reuse**. It will not:
bypass platform security, scrape unauthorized sources automatically, or
circumvent rate limits. Safety systems pause automation on rate-limit or
authentication errors and alert the administrator.
