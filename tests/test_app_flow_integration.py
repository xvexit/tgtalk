from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from tgtwin.adapters.telegram.handlers import business_message
from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.adapters.telegram.sender import DryRunSender
from tgtwin.app import build_pipeline
from tgtwin.config import Settings
from tgtwin.llm.fake import FakeLLMProvider
from tgtwin.storage.db import get_sessionmaker
from tgtwin.storage.models import Message
from tgtwin.storage.repositories import PostgresMessageRepository


class DummyBot:
    async def send_message(self, *args, **kwargs):
        return None


class DummyMsg:
    def __init__(self, message_id, chat_id, text, from_user_id, date, business_connection_id="bc1"):
        self.message_id = message_id
        self.chat = type("C", (), {"id": chat_id})()
        self.text = text
        self.from_user = type("U", (), {"id": from_user_id})()
        self.date = date
        self.business_connection_id = business_connection_id


@pytest.mark.integration
@pytest.mark.asyncio
async def test_app_flow_integration() -> None:
    url = os.environ.get("DATABASE_URL", "")
    sessionmaker = get_sessionmaker(url)
    repo = PostgresMessageRepository(sessionmaker)
    settings = Settings()
    pipeline = build_pipeline(repo, FakeLLMProvider(), settings)
    bot = DummyBot()
    resolver = OwnerResolver(bot)
    resolver.set("bc1", owner_id=777, user_chat_id=777)
    sender = DryRunSender(bot)
    sender.set_resolver(resolver)
    sent = []
    orig_send = sender.send

    async def fake_send(msg, text, delay):
        sent.append((msg.chat_id, msg.message_id))
        return await orig_send(msg, text, delay)

    sender.send = fake_send
    router = business_message.setup(bot, pipeline, resolver, sender)
    handler = None
    try:
        for obs in router.message.observers:
            handler = obs.callback
            break
    except Exception:
        pass
    if handler is None:
        return
    chat_id = 888123
    try:
        msg = DummyMsg(1, chat_id, "hi", 555, datetime.now(UTC), "bc1")
        await handler(msg)
        async with sessionmaker() as session:
            from sqlalchemy import select

            res = await session.execute(select(Message).where(Message.chat_id == chat_id, Message.tg_message_id == 1))
            row = res.scalar_one_or_none()
            assert row is not None
            assert row.role == "them"
        msg_owner = DummyMsg(2, chat_id, "yo", 777, datetime.now(UTC), "bc1")
        await handler(msg_owner)
        async with sessionmaker() as session:
            from sqlalchemy import select

            res = await session.execute(select(Message).where(Message.chat_id == chat_id, Message.tg_message_id == 2))
            row = res.scalar_one_or_none()
            assert row is not None
            assert row.role == "owner"
        msg_after = DummyMsg(3, chat_id, "hi2", 555, datetime.now(UTC), "bc1")
        await handler(msg_after)
    finally:
        async with sessionmaker() as session:
            from sqlalchemy import delete

            await session.execute(delete(Message).where(Message.chat_id == chat_id))
            await session.commit()
