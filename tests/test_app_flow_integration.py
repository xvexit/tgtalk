from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select

from tgtwin.adapters.telegram.handlers import business_message
from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.adapters.telegram.sender import TelegramBusinessSender
from tgtwin.app import build_pipeline
from tgtwin.config import Settings
from tgtwin.llm.fake import FakeLLMProvider
from tgtwin.storage.db import get_sessionmaker
from tgtwin.storage.models import Message, ReplyLog
from tgtwin.storage.repositories import PostgresMessageRepository, PostgresReplyLogRepository
from tests.fakes import DummyBot, DummyChat, DummyMsg

OWNER_ID = 777


@pytest.mark.integration
@pytest.mark.asyncio
async def test_app_flow_integration() -> None:
    url = os.environ.get("DATABASE_URL", "")
    sessionmaker = get_sessionmaker(url)
    repo = PostgresMessageRepository(sessionmaker)
    log_repo = PostgresReplyLogRepository(sessionmaker)
    settings = Settings(TAKEOVER_HOURS=3, HISTORY_LIMIT=30, MAX_REPLIES_PER_HOUR=10)
    pipeline = build_pipeline(repo, FakeLLMProvider(response="ок"), settings, log_repo, "персона")
    bot = DummyBot(next_message_id=500)
    resolver = OwnerResolver(bot)
    resolver.set("bc1", owner_id=OWNER_ID, user_chat_id=OWNER_ID)
    sender = TelegramBusinessSender(bot, repo, resolver)
    router = business_message.setup(bot, pipeline, resolver, sender, log_repo)
    handler = router.observers["business_message"].handlers[0].callback
    chat_id = 888124
    try:
        msg = DummyMsg(
            message_id=1,
            chat=DummyChat(chat_id=chat_id, full_name="Иван"),
            text="привет",
            from_user_id=555,
            date=datetime.now(UTC),
            business_connection_id="bc1",
        )
        await handler(msg)
        assert bot.send_message_calls == 1
        async with sessionmaker() as session:
            res = await session.execute(
                select(Message).where(Message.chat_id == chat_id, Message.tg_message_id == 500)
            )
            bot_row = res.scalar_one_or_none()
            assert bot_row is not None
            assert bot_row.role == "bot"
            res = await session.execute(
                select(ReplyLog).where(
                    ReplyLog.chat_id == chat_id, ReplyLog.trigger_message_id == 1
                )
            )
            log_row = res.scalar_one_or_none()
            assert log_row is not None
            assert log_row.reply == "ок"
            assert log_row.sent is True
            assert log_row.context["model"] == "deepseek-flash"
            assert log_row.context["history_ids"] == [1]
        msg_owner = DummyMsg(
            message_id=2,
            chat=DummyChat(chat_id=chat_id, full_name="Владелец"),
            text="я сам отвечу",
            from_user_id=OWNER_ID,
            date=datetime.now(UTC),
            business_connection_id="bc1",
        )
        await handler(msg_owner)
        assert bot.send_message_calls == 1
        msg_after = DummyMsg(
            message_id=3,
            chat=DummyChat(chat_id=chat_id, full_name="Иван"),
            text="привет ещё раз",
            from_user_id=555,
            date=datetime.now(UTC),
            business_connection_id="bc1",
        )
        await handler(msg_after)
        assert bot.send_message_calls == 1
    finally:
        async with sessionmaker() as session:
            await session.execute(delete(ReplyLog).where(ReplyLog.chat_id == chat_id))
            await session.execute(delete(Message).where(Message.chat_id == chat_id))
            await session.commit()
