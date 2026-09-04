# 🚀 Deployment — GitHub + Railway

> ℹ️ The development agent (Arena.ai) has **no access to your GitHub or Railway
> accounts**, so the final push/deploy is a short manual step. Everything is
> prepared: the local git repository contains the complete history, and this
> document gives exact click-by-click instructions.

## 1. Push to GitHub

```bash
cd memes-pages

# Option A — GitHub CLI
gh repo create memes-pages --private --source=. --push

# Option B — plain git
# create an empty repo named memes-pages on github.com first, then:
git remote add origin git@github.com:<your-username>/memes-pages.git
git push -u origin main
```

CI (`.github/workflows/ci.yml`) runs pytest + frontend build + ruff on push.

## 2. Railway project

Create a project at [railway.app](https://railway.app) → **Deploy from GitHub
repo** → select `memes-pages`. Then add services:

### 2.1 PostgreSQL
- New → Database → PostgreSQL. Nothing else to configure.
- Note the `DATABASE_URL` of the instance.

### 2.2 Redis (optional but recommended)
- New → Database → Redis.

### 2.3 Backend API
- New → GitHub repo → **root directory**: `/` (uses `docker/Dockerfile.python`)
- Actually simplest: create services from the repo and override:
  - **Start command**:
    `sh -c "alembic -c shared/alembic.ini upgrade head && python -m scripts.seed_admin && uvicorn app.main:app --host 0.0.0.0 --port 8000 --app-dir backend"`
  - **Variables** (per service):
    ```
    MEMES_ENV=production
    MEMES_SECRET_KEY=<openssl rand -hex 32>
    MEMES_DATABASE_URL=${{Postgres.DATABASE_URL}}
    MEMES_REDIS_URL=${{Redis.REDIS_URL}}
    MEMES_ADMIN_EMAIL=you@example.com
    MEMES_ADMIN_PASSWORD=<strong password>
    MEMES_CREDENTIAL_ENCRYPTION_KEY=<openssl rand -hex 32>
    MEMES_PUBLIC_MEDIA_BASE_URL=https://<backend-domain>/media
    ```
  - **Networking** → generate domain → port `8000`
  - Add a **volume** mounted at `/app/media` (so processed videos survive deploys)

### 2.4 Worker (Memes Pages Agent)
- Same repo, same Dockerfile
- **Start command**: `python -m worker.main`
- Same variables as backend (bot token not required but useful for alerts)

### 2.5 Telegram bot
- Same repo, same Dockerfile
- **Start command**: `python -m telegram_bot.bot`
- Variables: backend ones + `MEMES_BOT_TOKEN`, `MEMES_ADMIN_TELEGRAM_IDS`
- Optional webhook mode: set `MEMES_WEBHOOK_URL=https://<service-domain>` and
  expose port `8080` (the bot serves the webhook on `/telegram/webhook`)

### 2.6 Frontend
- Same repo — Railway detects the `frontend/` directory; set
  **root directory**: `frontend` (builds with `docker/Dockerfile.frontend`
  semantics via `railway.json` below, or use a Dockerfile service)
- Variables: `API_INTERNAL_URL=http://backend.railway.internal:8000`
- Networking → generate domain → port `3000`

> `railway.json` files for each service are included at the repo root
> (`docker/railway/*.json`) as templates.

## 3. First-run checklist

1. Backend logs show `alembic upgrade head` success + admin seed.
2. Open the frontend domain → login with `MEMES_ADMIN_EMAIL/PASSWORD`.
3. Add an RSS source → **Check now** → items appear in Trending (scored).
4. Add a destination account (platform *custom* = dry-run) → automation ON.
5. Dashboard → toggle **Automation Start**. The agent takes over:
   discovery → scoring → pipeline → queue → batch schedule → publish (dry-run).
6. For live publishing: set account credentials (encrypted) and switch
   Settings → Publishing mode to `live`.
7. For Instagram publishing set `MEMES_PUBLIC_MEDIA_BASE_URL` — the Graph API
   fetches the video from that public URL.

## 4. Scaling notes

- Every service is stateless; scale each independently on Railway.
- Heavy video work happens in the **worker** — give it ≥ 1 vCPU.
- Postgres: the workload is modest (tens of thousands of rows/month).
