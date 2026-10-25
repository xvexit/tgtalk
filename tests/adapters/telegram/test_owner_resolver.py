from __future__ import annotations

import pytest

from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.adapters.telegram.sender import DryRunSender


class FakeConnUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class FakeConn:
    def __init__(self, user: FakeConnUser, user_chat_id: int | None) -> None:
        self.user = user
        self.user_chat_id = user_chat_id


class BotStub:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn
        self.get_calls: list[str] = []
        self.sent: list[tuple[int, str]] = []

    async def get_business_connection(self, business_connection_id: str):
        self.get_calls.append(business_connection_id)
        return self.conn

    async def send_message(self, chat_id: int, text: str) -> None:
        self.sent.append((chat_id, text))


@pytest.mark.asyncio
async def test_get_saves_owner_and_chat_id() -> None:
    bot = BotStub(FakeConn(FakeConnUser(777), 555))
    resolver = OwnerResolver(bot)
    info = await resolver.get("bc1")
    assert info.owner_id == 777
    assert info.user_chat_id == 555
    assert resolver.user_chat_id("bc1") == 555
    await resolver.get("bc1")
    assert bot.get_calls == ["bc1"]


@pytest.mark.asyncio
async def test_notify_owner_uses_resolver_chat_id() -> None:
    bot = BotStub(FakeConn(FakeConnUser(777), 555))
    resolver = OwnerResolver(bot)
    await resolver.get("bc1")
    sender = DryRunSender(bot, resolver)
    await sender.notify_owner("bc1", "текст")
    assert bot.sent == [(555, "текст")]


@pytest.mark.asyncio
async def test_notify_owner_unknown_connection_skips(caplog) -> None:
    bot = BotStub(FakeConn(FakeConnUser(777), 555))
    resolver = OwnerResolver(bot)
    sender = DryRunSender(bot, resolver)
    await sender.notify_owner("нет-такой", "текст")
    assert bot.sent == []
    assert "notify_owner_no_chat_id" in caplog.text
