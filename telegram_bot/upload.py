"""Telegram video upload flow: video → caption → accounts → schedule."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from memes_shared.config import get_settings
from memes_shared.db.session import get_session
from memes_shared.models import DestinationAccount, DiscoveredContent, PublishingJob
from memes_shared.services.publishing import create_jobs_for_content, dispatch_due_jobs
from telegram_bot.formatting import truncate
from telegram_bot.guards import is_authorized
from telegram_bot.keyboards import UploadCB, upload_accounts_kb, upload_when_kb

router = Router(name="upload")


class UploadStates(StatesGroup):
    waiting_caption = State()
    waiting_accounts = State()
    waiting_when = State()


# local per-chat state for the flow (files are small; keep in memory)
_flow: dict[int, dict] = {}


@router.message(F.video | F.document)
async def receive_video(message: Message, state: FSMContext):
    if not is_authorized(message.from_user.id):
        return
    video = message.video or message.document
    if (video.file_size or 0) > 500 * 1024 * 1024:
        await message.answer("⛔️ File too large (max 500 MB).")
        return
    _flow[message.chat.id] = {
        "file_id": video.file_id,
        "file_name": getattr(video, "file_name", "") or "video.mp4",
        "title": message.caption or getattr(video, "file_name", "") or "Telegram upload",
    }
    await state.set_state(UploadStates.waiting_caption)
    await message.answer(
        f"🎬 Video received: <b>{truncate(_flow[message.chat.id]['title'], 50)}</b>\n\n"
        "📝 Send me the caption (or /default to use the default caption, "
        "/skip to skip):"
    )


@router.message(UploadStates.waiting_caption, F.text)
async def receive_caption(message: Message, state: FSMContext):
    flow = _flow.get(message.chat.id, {})
    if message.text == "/default":
        flow["caption"] = ""       # account default caption applies
    elif message.text == "/skip":
        flow["caption"] = ""
    else:
        flow["caption"] = message.text
    await state.set_state(UploadStates.waiting_accounts)
    with get_session() as s:
        accounts = (
            s.query(DestinationAccount)
            .filter(DestinationAccount.status == "active")
            .all()
        )
    if not accounts:
        await state.clear()
        await message.answer("⚠️ No active destination accounts. Add accounts first.")
        return
    flow["selected"] = {acc.id: False for acc in accounts}
    flow["account_ids"] = [acc.id for acc in accounts]
    await message.answer(
        "📱 Select destination accounts:",
        reply_markup=upload_accounts_kb(flow["selected"], accounts),
    )


@router.callback_query(UploadCB.filter(F.action == "acc"))
async def upload_toggle_account(call: CallbackQuery, callback_data: UploadCB,
                                state: FSMContext):
    flow = _flow.setdefault(call.chat.id, {})
    acc_id = int(callback_data.arg)
    selected = flow.setdefault("selected", {})
    selected[acc_id] = not selected.get(acc_id, False)
    with get_session() as s:
        accounts = s.query(DestinationAccount).filter(
            DestinationAccount.id.in_(flow.get("account_ids", [acc_id]))
        ).all()
    await call.message.edit_reply_markup(
        reply_markup=upload_accounts_kb(selected, accounts)
    )
    await call.answer()


@router.callback_query(UploadCB.filter(F.action == "all"))
async def upload_all_accounts(call: CallbackQuery, state: FSMContext):
    flow = _flow.setdefault(call.chat.id, {})
    flow["selected"] = {aid: True for aid in flow.get("account_ids", [])}
    with get_session() as s:
        accounts = s.query(DestinationAccount).filter(
            DestinationAccount.id.in_(flow.get("account_ids", [0]))
        ).all()
    await call.message.edit_reply_markup(
        reply_markup=upload_accounts_kb(flow["selected"], accounts)
    )
    await call.answer("all accounts selected")


@router.callback_query(UploadCB.filter(F.action == "cancel"))
async def upload_cancel(call: CallbackQuery, state: FSMContext):
    _flow.pop(call.chat.id, None)
    await state.clear()
    await call.answer("upload cancelled")
    await call.message.answer("✖️ Upload cancelled.")


@router.callback_query(UploadCB.filter(F.action == "next"))
async def upload_next(call: CallbackQuery, state: FSMContext):
    flow = _flow.get(call.chat.id, {})
    if not any((flow.get("selected") or {}).values()):
        await call.answer("select at least one account", show_alert=True)
        return
    await state.set_state(UploadStates.waiting_when)
    await call.message.edit_reply_markup(reply_markup=upload_when_kb())
    await call.answer()


@router.callback_query(UploadCB.filter(F.action == "when"))
async def upload_when(call: CallbackQuery, callback_data: UploadCB, state: FSMContext):
    flow = _flow.pop(call.chat.id, None)
    if flow is None:
        await call.answer("expired — send the video again", show_alert=True)
        return
    await call.answer("processing…")
    status_msg = await call.message.answer("⏳ Downloading & processing video…")

    cfg = get_settings()
    bot = call.bot
    file = await bot.get_file(flow["file_id"])
    dest = cfg.media_path / "uploads"
    dest.mkdir(parents=True, exist_ok=True)
    ext = "." + (flow["file_name"].rsplit(".", 1)[-1].lower() or "mp4")
    if ext not in (".mp4", ".mov", ".webm", ".m4v", ".mkv", ".avi"):
        ext = ".mp4"
    path = dest / f"tg_{uuid.uuid4().hex[:12]}{ext}"
    await bot.download_file(file.file_path, destination=str(path))

    content = DiscoveredContent(
        external_id=f"tg_{uuid.uuid4().hex[:12]}",
        title=flow["title"],
        url=f"upload://{path.name}",
        media_type="video",
        category="memes",
        description=flow.get("caption", ""),
        published_at=datetime.now(timezone.utc),
        discovered_at=datetime.now(timezone.utc),
        raw_metrics={"telegram_upload": True, "chat_id": call.chat.id},
        status="detected",
    )
    with get_session() as s:
        s.add(content)
        s.flush()
        # reuse the dashboard upload pipeline (validation, dedup, normalize)
        from backend.app.routers.content import _process_local_video  # helper below

        video, error = _process_local_video(s, content, str(path))
        if error:
            content.status = "failed"
            content.error = error
            s.commit()
            await status_msg.edit_text(f"🔴 Processing failed: {error[:300]}")
            return

        from memes_shared.services.publishing import create_jobs_for_content as _create

        target_ids = [aid for aid, ok in flow["selected"].items() if ok]
        content.target_account_ids = target_ids
        jobs = _create(s, content, video)
        if not jobs:
            content.status = "skipped"
            content.error = "no eligible destination accounts"
            s.commit()
            await status_msg.edit_text("⚠️ No eligible destination accounts matched.")
            return

        when = callback_data.arg
        if when == "now":
            content.status = "queued"
            stats = dispatch_due_jobs(s, force_job_ids=[j.id for j in jobs])
            s.commit()
            await status_msg.edit_text(
                f"🚀 Published to {stats.get('published', 0)} account(s) "
                f"(failed: {stats.get('failed', 0)}) — dry-run mode applies."
            )
        else:
            from datetime import timedelta

            from memes_shared.utils.timeutil import utcnow

            minutes = max(1, int(when))
            for j in jobs:
                j.status = "scheduled"
                j.publish_at = utcnow() + timedelta(minutes=minutes)
            content.status = "scheduled"
            s.commit()
            await status_msg.edit_text(
                f"🗓 Scheduled to {len(jobs)} account(s) in {minutes} minutes.\n"
                f"Queue: /menu → 📥 Queue"
            )
