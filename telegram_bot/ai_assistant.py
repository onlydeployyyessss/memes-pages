"""🤖 Ask Memes Pages AI — Telegram assistant backed by real DB data.

The AI answers ONLY from live database context that we gather before each
call — it can never invent numbers. If AI is unavailable (no key, budget
exceeded, provider error) we show that clearly and the platform keeps
running deterministically.
"""
from __future__ import annotations

import json

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from memes_shared.db.session import get_session
from memes_shared.models import DestinationAccount, DiscoveredContent, PublishingJob, TrendScore
from memes_shared.services.ai import get_ai
from memes_shared.services.reports import collect_period
from memes_shared.services.settings import get_setting
from memes_shared.utils.timeutil import utcnow
from telegram_bot.formatting import truncate
from telegram_bot.guards import is_authorized
from telegram_bot.keyboards import main_menu

router = Router(name="ai_assistant")


class AskStates(StatesGroup):
    waiting_question = State()


def build_context(session) -> dict:
    """Gather REAL data for the assistant (nothing invented by the AI)."""
    accounts = session.query(DestinationAccount).all()
    top = (
        session.query(DiscoveredContent, TrendScore)
        .join(TrendScore, TrendScore.content_id == DiscoveredContent.id)
        .order_by(TrendScore.score.desc())
        .limit(5)
        .all()
    )
    return {
        "generated_at": utcnow().isoformat(),
        "accounts": [
            {
                "username": a.username or a.name,
                "platform": a.platform,
                "followers": a.followers_count,
                "automation_enabled": a.automation_enabled,
                "status": a.status,
                "published_posts": session.query(PublishingJob)
                    .filter_by(account_id=a.id, status="published").count(),
            }
            for a in accounts
        ],
        "performance_7d": collect_period(session, 7),
        "queue": {
            "queued": session.query(PublishingJob).filter_by(status="queued").count(),
            "scheduled": session.query(PublishingJob).filter_by(status="scheduled").count(),
            "published_total": session.query(PublishingJob).filter_by(status="published").count(),
            "failed_total": session.query(PublishingJob).filter_by(status="failed").count(),
        },
        "top_trending": [
            {
                "title": truncate(c.title, 60),
                "trend_score": round(t.score, 1),
                "status": c.status,
                "category": c.category,
                "ai_reason": ((t.signals or {}).get("ai") or {}).get("reason", ""),
            }
            for c, t in top
        ],
    }


async def show_ask_ai(message: Message, state: FSMContext | None = None,
                      edit: bool = False):
    with get_session() as s:
        ai = get_ai(s)
        enabled = get_setting(s, "ai").get("assistant_enabled", True)
        configured = ai.configured and enabled
    if not configured:
        await message.answer(
            "🤖⚠️ <b>AI assistant is not available.</b>\n\n"
            "To enable it, set <code>OPENROUTER_API_KEY</code> as an environment "
            "variable (and keep AI enabled in Dashboard → 🤖 AI).\n\n"
            "Everything else keeps working deterministically."
        )
        return
    if state is not None:
        await state.set_state(AskStates.waiting_question)
    await message.answer(
        "🤖 <b>Ask Memes Pages AI</b>\n\n"
        "I answer from your live database: accounts, analytics, queue, "
        "trending.\n\n"
        "<i>Examples:</i>\n"
        "• Which account grew the fastest this week?\n"
        "• What type of content is performing best?\n"
        "• How many videos are currently queued?\n"
        "• Why did the top video get a high Trend Score?\n\n"
        "Send your question (or /cancel):"
    )


@router.message(AskStates.waiting_question, Command("cancel"))
async def cancel_ask(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("✖️ Cancelled.", reply_markup=main_menu())


@router.message(AskStates.waiting_question, F.text)
async def answer_question(message: Message, state: FSMContext):
    if not is_authorized(message.from_user.id):
        return
    question = (message.text or "").strip()
    await state.clear()
    if not question or question.startswith("/"):
        await message.answer("Use /menu to go back.")
        return

    waiting = await message.answer("🧠 Gathering live data & thinking…")
    with get_session() as s:
        context = build_context(s)
        ai = get_ai(s)
        answer = ""
        if ai.configured and get_setting(s, "ai").get("assistant_enabled", True):
            answer = ai.assistant_answer(question, json.dumps(context, default=str))
        s.commit()

    if not answer:
        # deterministic fallback — real numbers, no AI
        perf = context["performance_7d"]
        q = context["queue"]
        best = max(context["accounts"], key=lambda a: a["followers"], default=None)
        answer = (
            "⚠️ AI is unavailable right now (no API key, budget reached, or "
            "provider error) — automation continues deterministically.\n\n"
            f"📥 Queued: {q['queued']} + {q['scheduled']} scheduled\n"
            f"🟢 Published total: {q['published_total']} (failed: {q['failed_total']})\n"
            f"👁 Views 7d: {perf['views']:,}\n"
            f"👥 New followers 7d: +{perf['new_followers']:,}\n"
            + (f"📱 Biggest account: @{best['username']} ({best['followers']:,})"
               if best else "")
        )
    await waiting.edit_text(f"❓ <i>{truncate(question, 120)}</i>\n\n🤖 {answer[:3700]}")
