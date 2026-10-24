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
from tgtwin.adapters.telegram.sender import DryRunSender
from tgtwin.app import build_pipeline
from tgtwin.config import Settings
from tgtwin.llm.fake import FakeLLMProvider
from tgtwin.storage.db import get_sessionmaker
from tgtwin.storage.repositories import PostgresMessageRepository

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()
    if settings.SEND_ENABLED:
        raise RuntimeError("Реальная отправка появится на этапе 2")
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
    sender = DryRunSender(bot)
    llm = FakeLLMProvider()
    sessionmaker = get_sessionmaker(settings.DATABASE_URL)
    repo = PostgresMessageRepository(sessionmaker)
    pipeline = build_pipeline(repo, llm, settings)
    dp.include_router(business_connection.setup(bot, sender, resolver))
    dp.include_router(business_message.setup(bot, pipeline, resolver, sender))
    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)


if __name__ == "__main__":
    asyncio.run(main())
