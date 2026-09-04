"""Bot keyboards."""
from __future__ import annotations

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder


class SecCB(CallbackData, prefix="sec"):
    action: str
    arg: str = ""


class TrendCB(CallbackData, prefix="trend"):
    action: str   # preview | analytics | disablesrc | queue
    content_id: int


class AccCB(CallbackData, prefix="acc"):
    action: str   # toggle | settings
    account_id: int


class UploadCB(CallbackData, prefix="up"):
    action: str   # acc (toggle), next, cancel, mode, when
    arg: str = ""


def main_menu() -> ReplyKeyboardMarkup:
    b = ReplyKeyboardBuilder()
    rows = [
        ("📊 Dashboard",), ("📱 Accounts",), ("🔥 Trending",),
        ("🎬 Content",), ("📥 Queue",), ("📅 Schedule",),
        ("📝 Captions",), ("🖼 Covers",), ("📈 Analytics",),
        ("📄 Reports",), ("⚙️ Settings",), ("🟢 Automation",),
        ("🤖 Ask AI",), ("⬆️ Upload Video",),
    ]
    for (label,) in rows:
        b.button(text=label)
    b.adjust(2, 2, 2, 2, 2, 2, 2)
    return b.as_markup(resize_keyboard=True)


def section_home(back_action: str = "home") -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🔄 Refresh", callback_data=SecCB(action=back_action).pack())
    b.button(text="🏠 Main", callback_data=SecCB(action="home").pack())
    b.adjust(2)
    return b.as_markup()


def automation_kb(state: dict) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    if state.get("enabled") and not state.get("paused"):
        b.button(text="⏸ Pause", callback_data=SecCB(action="auto_pause").pack())
        b.button(text="⏹ Stop", callback_data=SecCB(action="auto_stop").pack())
    elif state.get("enabled"):
        b.button(text="▶ Resume", callback_data=SecCB(action="auto_resume").pack())
        b.button(text="⏹ Stop", callback_data=SecCB(action="auto_stop").pack())
    else:
        b.button(text="▶ Start", callback_data=SecCB(action="auto_start").pack())
    b.button(text="🔄 Run Now", callback_data=SecCB(action="auto_run").pack())
    b.button(text="🏠 Main", callback_data=SecCB(action="home").pack())
    b.adjust(2, 1, 1)
    return b.as_markup()


def trending_kb(content_id: int) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="👁 Preview", callback_data=TrendCB(action="preview", content_id=content_id).pack())
    b.button(text="📊 Analytics", callback_data=TrendCB(action="analytics", content_id=content_id).pack())
    b.button(text="🚫 Disable Source", callback_data=TrendCB(action="disablesrc", content_id=content_id).pack())
    b.button(text="📥 Force Queue", callback_data=TrendCB(action="queue", content_id=content_id).pack())
    b.adjust(2, 2)
    return b.as_markup()


def account_kb(account_id: int, enabled: bool) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🟢 Automation: ON" if enabled else "🔴 Automation: OFF",
             callback_data=AccCB(action="toggle", account_id=account_id).pack())
    b.button(text="📊 Metrics", callback_data=AccCB(action="metrics", account_id=account_id).pack())
    b.adjust(1, 1)
    return b.as_markup()


def upload_accounts_kb(selected: dict[int, bool], accounts: list) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for acc in accounts:
        mark = "☑" if selected.get(acc.id) else "☐"
        b.button(text=f"{mark} @{acc.username or acc.name}",
                 callback_data=UploadCB(action="acc", arg=str(acc.id)).pack())
    b.button(text="☑ All", callback_data=UploadCB(action="all").pack())
    b.button(text="Next ▶", callback_data=UploadCB(action="next").pack())
    b.button(text="✖ Cancel", callback_data=UploadCB(action="cancel").pack())
    b.adjust(1, 1, 1, 1, 3)
    return b.as_markup()


def upload_when_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="🚀 Publish Now", callback_data=UploadCB(action="when", arg="now").pack())
    b.button(text="🕐 In 1 hour", callback_data=UploadCB(action="when", arg="60").pack())
    b.button(text="🗓 In 6 hours", callback_data=UploadCB(action="when", arg="360").pack())
    b.button(text="✖ Cancel", callback_data=UploadCB(action="cancel").pack())
    b.adjust(1, 2, 1)
    return b.as_markup()
