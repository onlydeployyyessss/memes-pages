"""Telegram notifications to administrators (independent of aiogram)."""
from __future__ import annotations

import httpx
from sqlalchemy.orm import Session

from memes_shared.config import get_settings
from memes_shared.db.session import SessionLocal
from memes_shared.logging_setup import get_logger
from memes_shared.models import User

log = get_logger("memes.notifier")


def get_recipients(session: Session | None = None) -> list[int]:
    """Admin Telegram IDs = env config + admin users with notifications on."""
    own_session = session is None
    s = session or SessionLocal()
    try:
        ids = set(get_settings().admin_ids)
        for u in s.query(User).filter(
            User.is_admin.is_(True),
            User.is_active.is_(True),
            User.notifications_enabled.is_(True),
            User.telegram_id.isnot(None),
        ):
            ids.add(int(u.telegram_id))
        return sorted(ids)
    finally:
        if own_session:
            s.close()


def send_telegram(chat_id: int, text: str) -> bool:
    token = get_settings().bot_token
    if not token:
        log.debug("no bot token configured — notification suppressed: %s", text[:80])
        return False
    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text[:4000]},
            timeout=15.0,
        )
        if resp.status_code == 403:
            log.warning("recipient %s blocked the bot — disabling their notifications", chat_id)
            with SessionLocal() as s:  # type: ignore[misc]
                u = s.query(User).filter(User.telegram_id == chat_id).first()
                if u:
                    u.notifications_enabled = False
                    s.commit()
            return False
        return resp.status_code == 200
    except httpx.HTTPError as e:
        log.warning("telegram send failed: %s", e)
        return False


def notify_admins(text: str, session: Session | None = None) -> int:
    recipients = get_recipients(session)
    sent = 0
    for chat_id in recipients:
        if send_telegram(chat_id, text):
            sent += 1
    return sent
