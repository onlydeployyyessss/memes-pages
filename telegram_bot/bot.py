"""Telegram bot entrypoint — polling (default) or webhook.

Run: python -m telegram_bot.bot
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "shared"))

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from memes_shared.config import get_settings
from memes_shared.logging_setup import get_logger, setup_logging

setup_logging()
log = get_logger("memes.bot")


def build_dispatcher() -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())
    from telegram_bot.handlers import router as sections_router
    from telegram_bot.upload import router as upload_router

    dp.include_router(sections_router)
    dp.include_router(upload_router)
    return dp


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    log.info("bot starting in polling mode")
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])


async def run_webhook(bot: Bot, dp: Dispatcher, base_url: str, secret: str) -> None:
    from aiogram.webhook.aiohttp_server import (
        SimpleRequestHandler,
        setup_application,
    )

    from aiohttp import web

    path = "/telegram/webhook"
    await bot.set_webhook(f"{base_url.rstrip('/')}{path}", secret_token=secret or "")
    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot,
                         secret_token=secret or "").register(app, path)
    setup_application(app, dp, bot=bot)
    log.info("bot starting in webhook mode: %s", base_url)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    await asyncio.Event().wait()


def main() -> None:
    cfg = get_settings()
    if not cfg.bot_token:
        print("MEMES_BOT_TOKEN is not set — cannot start the bot.")
        print("Create a bot with @BotFather and put the token into .env")
        sys.exit(1)
    bot = Bot(token=cfg.bot_token,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = build_dispatcher()

    if cfg.webhook_url:
        asyncio.run(run_webhook(bot, dp, cfg.webhook_url, cfg.webhook_secret))
    else:
        asyncio.run(run_polling(bot, dp))


if __name__ == "__main__":
    main()
