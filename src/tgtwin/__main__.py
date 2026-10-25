from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode

from tgtwin.adapters.telegram.handlers import business_connection, business_message
from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.adapters.telegram.router import ALLOWED_UPDATES
from tgtwin.app import build_pipeline, choose_llm, choose_sender, validate_startup
from tgtwin.config import Settings
from tgtwin.steps.build_context import load_persona
from tgtwin.storage.db import get_sessionmaker
from tgtwin.storage.repositories import PostgresMessageRepository, PostgresReplyLogRepository

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()
    persona_text = ""
    try:
        persona_text = load_persona(settings.PERSONA_PATH)
    except OSError:
        persona_text = ""
    validate_startup(settings, persona_text)
    session = None
    if settings.TELEGRAM_PROXY:
        session = AiohttpSession(proxy=settings.TELEGRAM_PROXY)
        logger.info("proxy enabled")
    bot = Bot(
        token=settings.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        session=session,
    )
    dp = Dispatcher()
    resolver = OwnerResolver(bot)
    sessionmaker = get_sessionmaker(settings.DATABASE_URL)
    repo = PostgresMessageRepository(sessionmaker)
    log_repo = PostgresReplyLogRepository(sessionmaker)
    llm = choose_llm(settings)
    sender = choose_sender(settings, bot, repo, resolver)
    pipeline = build_pipeline(repo, llm, settings, log_repo, persona_text)
    dp.include_router(business_connection.setup(bot, sender, resolver))
    dp.include_router(business_message.setup(bot, pipeline, resolver, sender, log_repo))
    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)


if __name__ == "__main__":
    asyncio.run(main())
