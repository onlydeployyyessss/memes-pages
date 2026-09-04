# Unified entrypoint — dispatches the process to run based on $ROLE.
#
#   ROLE=api       (default) migrate → seed admin → serve FastAPI on :8000
#   ROLE=worker              start the APScheduler automation worker
#   ROLE=telegram-bot        start the aiogram polling bot
#
# Any other value falls through to the default CMD (api server).
set -e

ROLE="${ROLE:-api}"

# backend.app.* imports expect the repo root on sys.path (uvicorn --app-dir
# puts only /app/backend there; PYTHONPATH restores /app).
export PYTHONPATH="/app${PYTHONPATH:+:${PYTHONPATH}}"

case "$ROLE" in
  worker)
    alembic -c shared/alembic.ini upgrade head
    exec python -m worker.main
    ;;
  telegram-bot)
    alembic -c shared/alembic.ini upgrade head
    exec python -m telegram_bot.bot
    ;;
  *)
    # api: self-migrating, self-seeding server (same recipe as docker-compose)
    alembic -c shared/alembic.ini upgrade head
    python -m scripts.seed_admin
    exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --app-dir backend
    ;;
esac
