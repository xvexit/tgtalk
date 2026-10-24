from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from tgtwin.adapters.telegram.handlers import business_connection, business_message
from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.adapters.telegram.router import ALLOWED_UPDATES
from tgtwin.adapters.telegram.sender import DryRunSender
from tgtwin.app import build_pipeline
from tgtwin.config import Settings
from tgtwin.llm.fake import FakeLLMProvider
from tgtwin.storage.db import get_sessionmaker

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    settings = Settings()
    if settings.SEND_ENABLED:
        raise RuntimeError("Реальная отправка появится на этапе 2")
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    resolver = OwnerResolver(bot)
    sender = DryRunSender(bot)
    llm = FakeLLMProvider()
    sessionmaker = get_sessionmaker(settings.DATABASE_URL)
    async with sessionmaker() as session:
        repo = None
        try:
            from tgtwin.storage.repositories import PostgresMessageRepository

            repo = PostgresMessageRepository(session)
        except Exception:
            repo = None
    pipeline = build_pipeline(llm)
    dp.include_router(business_connection.setup(bot, sender, resolver))
    dp.include_router(business_message.setup(bot, pipeline, resolver))
    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)


if __name__ == "__main__":
    asyncio.run(main())
