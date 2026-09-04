"""Bot section handlers — Dashboard, Accounts, Trending, Queue, Schedule,
Captions, Covers, Analytics, Reports, Settings, Automation."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from memes_shared.db.session import get_session
from memes_shared.models import (
    Caption,
    ContentSource,
    DestinationAccount,
    DiscoveredContent,
    PublishingJob,
    ReelCover,
    TrendScore,
)
from memes_shared.services import automation as automation_svc
from memes_shared.services.settings import get_setting
from sqlalchemy import func

from telegram_bot.formatting import ago, fmt_int, st, trend_line, truncate
from telegram_bot.guards import is_authorized, register_or_update
from telegram_bot.keyboards import (
    AccCB,
    SecCB,
    TrendCB,
    automation_kb,
    main_menu,
    section_home,
)

router = Router(name="sections")

SECTION_BY_TEXT = {
    "📊 Dashboard": "dashboard", "📱 Accounts": "accounts", "🔥 Trending": "trending",
    "🎬 Content": "content", "📥 Queue": "queue", "📅 Schedule": "schedule",
    "📝 Captions": "captions", "🖼 Covers": "covers", "📈 Analytics": "analytics",
    "📄 Reports": "reports", "⚙️ Settings": "settings", "🟢 Automation": "automation",
    "🤖 Ask AI": "ask_ai",
}


# ── Entry ────────────────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message):
    register_or_update(message)
    if not is_authorized(message.from_user.id):
        await message.answer(
            "⛔️ You are not authorized to use this bot.\n"
            "Ask the administrator to add your Telegram ID: "
            f"<code>{message.from_user.id}</code>"
        )
        return
    await message.answer(
        "🤖 <b>MEMES PAGES</b>\n\n"
        "Content discovery • management • analytics • publishing automation\n\n"
        "Choose a section below ⬇️",
        reply_markup=main_menu(),
    )


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    if is_authorized(message.from_user.id):
        await message.answer("🤖 <b>MEMES PAGES</b>", reply_markup=main_menu())


@router.message(Command("id"))
async def cmd_id(message: Message):
    await message.answer(f"Your Telegram ID: <code>{message.from_user.id}</code>")


@router.message(F.text.in_(SECTION_BY_TEXT.keys()))
async def section_entry(message: Message, state: FSMContext = None):
    if not is_authorized(message.from_user.id):
        return
    section = SECTION_BY_TEXT[message.text]
    if section == "ask_ai":
        from telegram_bot.ai_assistant import show_ask_ai

        await show_ask_ai(message, state=state)
        return
    handler = {
        "dashboard": show_dashboard, "accounts": show_accounts,
        "trending": show_trending, "content": show_content, "queue": show_queue,
        "schedule": show_schedule, "captions": show_captions, "covers": show_covers,
        "analytics": show_analytics, "reports": show_reports, "settings": show_settings,
        "automation": show_automation,
    }[section]
    await handler(message)


@router.callback_query(SecCB.filter(F.action != "home"))
async def sec_callback(call: CallbackQuery, callback_data: SecCB):
    if not is_authorized(call.from_user.id):
        await call.answer("not authorized", show_alert=True)
        return
    handler = {
        "dashboard": show_dashboard, "accounts": show_accounts,
        "trending": show_trending, "content": show_content, "queue": show_queue,
        "schedule": show_schedule, "captions": show_captions, "covers": show_covers,
        "analytics": show_analytics, "reports": show_reports, "settings": show_settings,
        "automation": show_automation,
    }.get(callback_data.action)
    if handler is None:
        await call.answer()
        return
    await handler(call.message, edit=True)
    await call.answer()


@router.callback_query(SecCB.filter(F.action == "home"))
async def home_callback(call: CallbackQuery):
    await call.message.answer("🤖 <b>MEMES PAGES</b>", reply_markup=main_menu())
    await call.answer()


# ── Dashboard ────────────────────────────────────────────────────────
async def show_dashboard(message: Message, edit: bool = False):
    with get_session() as s:
        accounts = s.query(DestinationAccount).count()
        active = s.query(DestinationAccount).filter(DestinationAccount.status == "active").count()
        detected = s.query(DiscoveredContent).count()
        queued = s.query(PublishingJob).filter(PublishingJob.status.in_(["queued", "scheduled"])).count()
        published = s.query(PublishingJob).filter(PublishingJob.status == "published").count()
        failed = s.query(PublishingJob).filter(PublishingJob.status == "failed").count()
        followers = s.query(func.coalesce(func.sum(DestinationAccount.followers_count), 0)).scalar()
        state = automation_svc.status_summary(s)
        sources = s.query(ContentSource).filter(ContentSource.authorization == "authorized").count()
    text = (
        "📊 <b>MEMES PAGES — Dashboard</b>\n\n"
        f"📱 Accounts: <b>{accounts}</b> ({active} active)\n"
        f"🔐 Authorized sources: <b>{sources}</b>\n"
        f"🎬 Videos detected: <b>{detected}</b>\n"
        f"📥 Queue: <b>{queued}</b>\n"
        f"🟢 Published: <b>{published}</b>  •  🔴 Failed: <b>{failed}</b>\n"
        f"👥 Total followers: <b>{fmt_int(followers)}</b>\n\n"
        f"{state['label']}\n"
        f"⏱ Last run: {state['last_run_ago']} ({state['last_run_job'] or '—'})\n"
        f"⏭ Next post: {state['next_run'][:16].replace('T', ' ') or '—'}"
    )
    await _send(message, text, section_home("dashboard"), edit)


# ── Accounts ─────────────────────────────────────────────────────────
async def show_accounts(message: Message, edit: bool = False):
    with get_session() as s:
        accounts = s.query(DestinationAccount).order_by(DestinationAccount.id).all()
        parts = ["📱 <b>Destination Accounts</b>\n"]
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        kb = InlineKeyboardBuilder()
        for acc in accounts:
            parts.append(
                f"{st(acc.status)} <b>@{acc.username or acc.name}</b>\n"
                f"👥 {fmt_int(acc.followers_count)} followers • "
                f"Automation: {'ON' if acc.automation_enabled else 'OFF'} • "
                f"API: {acc.integration_status}\n"
                f"🕒 Last post: {ago(acc.last_publish_at)}\n"
            )
            kb.button(
                text=f"{'🟢' if acc.automation_enabled else '🔴'} @{acc.username or acc.name}",
                callback_data=AccCB(action="toggle", account_id=acc.id).pack(),
            )
        if not accounts:
            parts.append("No accounts yet — add them on the Web Dashboard.")
        kb.button(text="🏠 Main", callback_data=SecCB(action="home").pack())
        kb.adjust(1)
        await _send(message, "\n".join(parts), kb.as_markup(), edit)


@router.callback_query(AccCB.filter(F.action == "toggle"))
async def account_toggle(call: CallbackQuery, callback_data: AccCB):
    if not is_authorized(call.from_user.id):
        return
    with get_session() as s:
        acc = s.get(DestinationAccount, callback_data.account_id)
        if acc:
            acc.automation_enabled = not acc.automation_enabled
            name, enabled = f"@{acc.username or acc.name}", acc.automation_enabled
    await call.answer(f"{name}: automation {'ON' if enabled else 'OFF'}")
    await show_accounts(call.message, edit=True)


@router.callback_query(AccCB.filter(F.action == "metrics"))
async def account_metrics(call: CallbackQuery, callback_data: AccCB):
    with get_session() as s:
        acc = s.get(DestinationAccount, callback_data.account_id)
        if acc is None:
            await call.answer("account not found", show_alert=True)
            return
        text = (
            f"📊 <b>@{acc.username or acc.name}</b>\n\n"
            f"👥 Followers: {fmt_int(acc.followers_count)}\n"
            f"🟢 Published posts: {s.query(PublishingJob).filter_by(account_id=acc.id, status='published').count()}\n"
            f"🔴 Failed: {s.query(PublishingJob).filter_by(account_id=acc.id, status='failed').count()}\n"
            f"🕒 Last post: {ago(acc.last_publish_at)}\n"
            f"🔗 Integration: {acc.integration_status}"
        )
    await call.answer()
    await call.message.answer(text)


# ── Trending ─────────────────────────────────────────────────────────
async def show_trending(message: Message, edit: bool = False):
    with get_session() as s:
        rows = (
            s.query(DiscoveredContent, TrendScore, ContentSource)
            .join(TrendScore, TrendScore.content_id == DiscoveredContent.id)
            .outerjoin(ContentSource, ContentSource.id == DiscoveredContent.source_id)
            .order_by(TrendScore.score.desc())
            .limit(5)
            .all()
        )
        if not rows:
            await _send(message, "🔥 <b>TRENDING</b>\n\nNo scored content yet. "
                                 "Add RSS feeds or authorized sources and run discovery.",
                        section_home("trending"), edit)
            return
        parts = ["🔥 <b>TRENDING CONTENT</b>\n"]
        for content, ts, source in rows:
            parts.append(
                f"<b>{truncate(content.title, 48)}</b>\n"
                f"{trend_line(ts.score, ts.signals or {})}\n"
                f"📁 {content.category} • {st(content.status)} {content.status}\n"
                f"📡 Source: {source.name if source else 'manual'} "
                f"({source.authorization if source else '—'})\n"
                f"🆔 <code>{content.id}</code>\n"
            )
        kb = section_home("trending")
        from aiogram.utils.keyboard import InlineKeyboardBuilder

        builder = InlineKeyboardBuilder()
        for content, ts, _source in rows[:5]:
            builder.button(text=f"⚡ {ts.score:.0f} — {truncate(content.title, 22)}",
                           callback_data=TrendCB(action="preview", content_id=content.id).pack())
        builder.adjust(1)
        from aiogram.types import InlineKeyboardMarkup

        merged = InlineKeyboardMarkup(inline_keyboard=[
            *builder.as_markup().inline_keyboard,
            *kb.inline_keyboard,
        ])
        await _send(message, "\n".join(parts), merged, edit)


@router.callback_query(TrendCB.filter())
async def trend_action(call: CallbackQuery, callback_data: TrendCB):
    if not is_authorized(call.from_user.id):
        return
    with get_session() as s:
        content = s.get(DiscoveredContent, callback_data.content_id)
        if content is None:
            await call.answer("content not found", show_alert=True)
            return
        ts = s.query(TrendScore).filter_by(content_id=content.id).first()
        if callback_data.action == "preview":
            await call.answer()
            await call.message.answer(
                f"👁 <b>{truncate(content.title, 60)}</b>\n\n"
                f"{content.url or content.media_url or '(no url)'}\n\n"
                f"{trend_line(ts.score if ts else 0, (ts.signals if ts else {}) or {})}\n\n"
                f"Status: {st(content.status)} {content.status}"
            )
        elif callback_data.action == "analytics":
            events = s.query(PublishingJob).filter_by(content_id=content.id).all()
            published = [j for j in events if j.status == "published"]
            await call.answer()
            await call.message.answer(
                f"📊 <b>Content analytics</b>\n\n"
                f"Title: {truncate(content.title, 50)}\n"
                f"Score: {ts.score if ts else '—'}/100\n"
                f"Jobs: {len(events)} total • {len(published)} published\n"
                f"Accounts: " + ", ".join(f"@{s.get(DestinationAccount, j.account_id).username or s.get(DestinationAccount, j.account_id).name}" for j in events if s.get(DestinationAccount, j.account_id)) +
                f"\nMetrics: {(content.raw_metrics or {})}"
            )
        elif callback_data.action == "disablesrc":
            if content.source_id:
                src = s.get(ContentSource, content.source_id)
                src.enabled = False
                s.commit()
                await call.answer(f"source '{src.name}' disabled", show_alert=True)
            else:
                await call.answer("content has no source", show_alert=True)
        elif callback_data.action == "queue":
            from memes_shared.services.pipeline import process_content

            content.status = "processing"
            s.flush()
            result = process_content(s, content)
            s.commit()
            await call.answer(f"pipeline result: {result}", show_alert=True)


# ── Content ──────────────────────────────────────────────────────────
async def show_content(message: Message, edit: bool = False):
    with get_session() as s:
        counts = dict(
            s.query(DiscoveredContent.status, func.count(DiscoveredContent.id))
            .group_by(DiscoveredContent.status).all()
        )
        recent = s.query(DiscoveredContent).order_by(DiscoveredContent.discovered_at.desc()).limit(8).all()
    lines = ["🎬 <b>Content Library</b>\n"]
    for status in ("detected", "processing", "queued", "scheduled", "published", "failed"):
        if counts.get(status):
            lines.append(f"{st(status)} {status}: <b>{counts[status]}</b>")
    lines.append("\n<b>Recent:</b>")
    for row in recent:
        lines.append(f"{st(row.status)} {truncate(row.title, 42)} ({row.category})")
    lines.append("\n⬆️ Send me a video file to upload & schedule it.")
    await _send(message, "\n".join(lines), section_home("content"), edit)


# ── Queue ────────────────────────────────────────────────────────────
async def show_queue(message: Message, edit: bool = False):
    with get_session() as s:
        jobs = (
            s.query(PublishingJob, DestinationAccount)
            .join(DestinationAccount, DestinationAccount.id == PublishingJob.account_id)
            .filter(PublishingJob.status.in_(["queued", "scheduled", "publishing"]))
            .order_by(PublishingJob.publish_at.is_(None), PublishingJob.publish_at)
            .limit(10)
            .all()
        )
        total = s.query(PublishingJob).filter(PublishingJob.status.in_(["queued", "scheduled"])).count()
        failed = s.query(PublishingJob).filter(PublishingJob.status == "failed").count()
    lines = [f"📥 <b>Publishing Queue</b> — {total} pending • {failed} failed\n"]
    for job, acc in jobs:
        when = job.publish_at.strftime("%d %b %H:%M") if job.publish_at else "awaiting schedule"
        lines.append(f"{st(job.status)} {when} UTC → @{acc.username or acc.name} (#{job.id})")
    if not jobs:
        lines.append("Queue is empty.")
    await _send(message, "\n".join(lines), section_home("queue"), edit)


# ── Schedule ─────────────────────────────────────────────────────────
async def show_schedule(message: Message, edit: bool = False):
    with get_session() as s:
        cfg = get_setting(s, "scheduler")
        state = automation_svc.status_summary(s)
    text = (
        "📅 <b>Batch Publishing Scheduler</b>\n\n"
        f"Batch size: <b>{cfg.get('batch_size')}</b>\n"
        f"Initial delay: <b>{cfg.get('initial_delay_minutes')} min</b>\n"
        f"Gap between posts: <b>{cfg.get('min_delay_minutes')}–{cfg.get('max_delay_minutes')} min</b>"
        f" (fixed: {cfg.get('fixed_delay_minutes') or 'variable'})\n"
        f"Rest between batches: <b>{cfg.get('rest_period_minutes', 0) / 60:.1f} h</b>\n"
        f"Posting window: <b>{cfg.get('post_window_start')}:00–{cfg.get('post_window_end')}:00</b>\n"
        f"Quiet hours: <b>{cfg.get('quiet_hours_start') or '—'}–{cfg.get('quiet_hours_end') or '—'}</b>\n"
        f"Max posts/day: <b>{cfg.get('max_posts_per_day')}</b>\n"
        f"Timezone: <b>{cfg.get('timezone')}</b>\n\n"
        f"⏭ Next post: {state['next_run'][:16].replace('T', ' ') or '—'}\n"
        f"⚙️ Configure via Dashboard → Schedule"
    )
    await _send(message, text, section_home("schedule"), edit)


# ── Captions / Covers ────────────────────────────────────────────────
async def show_captions(message: Message, edit: bool = False):
    from memes_shared.models import CaptionTemplate

    with get_session() as s:
        captions = s.query(Caption).order_by(Caption.id).all()
        templates = s.query(CaptionTemplate).count()
    lines = ["📝 <b>Captions</b>\n"]
    for c in captions:
        star = " ⭐" if c.is_default else ""
        lines.append(f"• <b>{c.name}</b>{star}\n<code>{truncate(c.text, 90)}</code>")
    lines.append(f"\n🧩 Templates: {templates} (weighted random selection)")
    lines.append("Manage via Dashboard → Captions")
    await _send(message, "\n".join(lines), section_home("captions"), edit)


async def show_covers(message: Message, edit: bool = False):
    with get_session() as s:
        covers = s.query(ReelCover).order_by(ReelCover.id).all()
        accounts = s.query(DestinationAccount).filter(DestinationAccount.reel_cover_id.isnot(None)).count()
    lines = ["🖼 <b>Reel Covers</b>\n"]
    for c in covers:
        star = " ⭐ default" if c.is_default else ""
        lines.append(f"• {c.name} ({c.width}x{c.height}){star}")
    if not covers:
        lines.append("No covers uploaded yet.")
    lines.append(f"\nAssigned to {accounts} account(s)")
    lines.append("Upload & assign via Dashboard → Covers")
    await _send(message, "\n".join(lines), section_home("covers"), edit)


# ── Analytics / Reports ──────────────────────────────────────────────
async def show_analytics(message: Message, edit: bool = False):
    from memes_shared.services.reports import collect_period

    with get_session() as s:
        d = collect_period(s, 7)
    text = (
        "📈 <b>Analytics — last 7 days</b>\n\n"
        f"🎬 Published: <b>{d['published']}</b>\n"
        f"👁 Views: <b>{fmt_int(d['views'])}</b>\n"
        f"❤️ Likes: {fmt_int(d['likes'])}  💬 {fmt_int(d['comments'])}  ↗️ {fmt_int(d['shares'])}\n"
        f"👥 New followers: <b>+{fmt_int(d['new_followers'])}</b>\n"
        f"💪 Engagement: <b>{d['engagement_pct']}%</b> ({'+' if d['engagement_delta_pct'] >= 0 else ''}{d['engagement_delta_pct']}%)\n"
        + (f"\n🔥 Best account: @{d['best_account']}" if d.get("best_account") else "")
    )
    await _send(message, text, section_home("analytics"), edit)


async def show_reports(message: Message, edit: bool = False):
    from memes_shared.models import Report

    with get_session() as s:
        latest = s.query(Report).order_by(Report.id.desc()).limit(5).all()
    lines = ["📄 <b>Reports</b>\n"]
    for r in latest:
        lines.append(f"{st('published') if r.status == 'sent' else '•'} "
                     f"{r.report_type} — {ago(r.created_at)}\n<code>{truncate(r.text_content, 160)}</code>\n")
    if not latest:
        lines.append("No reports yet — generated daily at 21:05 UTC.")
    await _send(message, "\n".join(lines), section_home("reports"), edit)


# ── Settings ─────────────────────────────────────────────────────────
async def show_settings(message: Message, edit: bool = False):
    with get_session() as s:
        rules = get_setting(s, "rules")
        pub = get_setting(s, "publishing")
        notif = get_setting(s, "notifications")
    text = (
        "⚙️ <b>Settings</b>\n\n"
        "<b>Rule engine</b>\n"
        f"• Min trend score: <b>{rules.get('min_trend_score')}</b>\n"
        f"• Min engagement: <b>{rules.get('min_engagement')}</b>\n"
        f"• Max content age: <b>{rules.get('max_age_hours')}h</b>\n"
        f"• Max videos/day: <b>{rules.get('max_videos_per_day')}</b>\n"
        f"• Require authorized source: <b>{rules.get('require_authorized_source')}</b>\n"
        f"• Blocked keywords: {', '.join(rules.get('blocked_keywords') or []) or '—'}\n\n"
        f"<b>Publishing mode</b>: <b>{pub.get('mode')}</b> "
        f"({'dry-run — nothing touches real platforms' if pub.get('mode') == 'dry_run' else 'LIVE — official platform APIs'})\n\n"
        f"<b>Notifications</b>: trend ≥{notif.get('trend_hot_min_score')}, "
        f"milestones every {notif.get('milestone_follower_step')} followers\n\n"
        "Change on Dashboard → Settings"
    )
    await _send(message, text, section_home("settings"), edit)


# ── Automation ───────────────────────────────────────────────────────
async def show_automation(message: Message, edit: bool = False):
    with get_session() as s:
        state = automation_svc.status_summary(s)
    text = (
        f"{state['label']}\n\n"
        f"⏱ Last run: {state['last_run_ago']} ({state['last_run_job'] or '—'})\n"
        f"⏭ Next post: {state['next_run'][:16].replace('T', ' ') or '—'}\n"
        f"📥 Queue: {state['queue_size'] + state['scheduled_count']}\n"
        f"⚙️ Active jobs: {state['active_jobs']}\n"
        f"🔴 Failed jobs: {state['failed_jobs']}\n"
        + (f"\n⚠️ {state['stop_reason']}" if state.get("stop_reason") else "")
    )
    await _send(message, text, automation_kb(state), edit)


@router.callback_query(SecCB.filter(F.action.startswith("auto_")))
async def automation_actions(call: CallbackQuery, callback_data: SecCB):
    if not is_authorized(call.from_user.id):
        await call.answer("not authorized", show_alert=True)
        return
    action = callback_data.action.replace("auto_", "")
    with get_session() as s:
        if action == "start":
            automation_svc.start(s)
        elif action == "pause":
            automation_svc.pause(s)
        elif action == "resume":
            automation_svc.resume(s)
        elif action == "stop":
            automation_svc.stop(s, "stopped via Telegram")
        elif action == "run":
            automation_svc.request_run(s)
        s.commit()
    await call.answer(f"automation: {action}")
    await show_automation(call.message, edit=True)


# ── Helper ───────────────────────────────────────────────────────────
async def _send(message: Message, text: str, keyboard, edit: bool):
    if message is None:
        return
    if edit:
        try:
            await message.edit_text(text, reply_markup=keyboard)
            return
        except Exception:
            pass
    await message.answer(text, reply_markup=keyboard)
