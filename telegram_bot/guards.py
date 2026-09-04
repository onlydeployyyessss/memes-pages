"""Admin access gate for bot handlers."""
from __future__ import annotations

from aiogram.types import Message
from memes_shared.config import get_settings
from memes_shared.db.session import get_session
from memes_shared.models import User


def is_authorized(telegram_id: int) -> bool:
    if telegram_id in get_settings().admin_ids:
        return True
    with get_session() as s:
        row = (
            s.query(User)
            .filter(User.telegram_id == telegram_id, User.is_admin.is_(True),
                    User.is_active.is_(True))
            .first()
        )
        return row is not None


def register_or_update(message: Message) -> None:
    tg = message.from_user
    if tg is None:
        return
    with get_session() as s:
        row = s.query(User).filter(User.telegram_id == tg.id).first()
        if row is None:
            promoted = tg.id in get_settings().admin_ids
            s.add(User(
                telegram_id=tg.id, username=tg.username or "",
                first_name=tg.first_name or "", is_admin=promoted,
            ))
        else:
            row.username = tg.username or row.username
            row.first_name = tg.first_name or row.first_name
            row.last_seen_at = __import__("memes_shared.utils.timeutil", fromlist=["utcnow"]).utcnow()
