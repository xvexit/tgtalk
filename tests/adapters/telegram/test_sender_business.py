from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.fakes import DummyBot, FakeMessageRepo
from tgtwin.adapters.telegram.sender import TelegramBusinessSender
from tgtwin.core.models import IncomingMessage


def incoming() -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        connection_id="bc1",
        chat_id=1,
        message_id=1,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )


async def test_typing_and_send_with_business_connection(monkeypatch) -> None:
    sleep_calls: list[float] = []
    monkeypatch.setattr(
        "tgtwin.adapters.telegram.sender.asyncio.sleep", _sleep_recorder(sleep_calls)
    )
    bot = DummyBot(next_message_id=321)
    repo = FakeMessageRepo()
    sender = TelegramBusinessSender(bot, repo)
    message_id = await sender.send(incoming(), "ответ", 2.5)
    assert bot.send_chat_action_calls == 1
    assert bot.last_chat_action_kwargs["business_connection_id"] == "bc1"
    assert bot.last_chat_action_kwargs["chat_id"] == 1
    assert sleep_calls == [2.5]
    assert bot.send_message_calls == 1
    assert bot.last_send_kwargs["business_connection_id"] == "bc1"
    assert bot.last_send_kwargs["chat_id"] == 1
    assert bot.last_send_kwargs["text"] == "ответ"
    assert message_id == 321


def _sleep_recorder(calls: list[float]):
    async def fake_sleep(seconds: float) -> None:
        calls.append(seconds)

    return fake_sleep


async def test_bot_message_recorded() -> None:
    bot = DummyBot(next_message_id=321)
    repo = FakeMessageRepo()
    sender = TelegramBusinessSender(bot, repo)
    await sender.send(incoming(), "ответ", 0)
    stored = repo.rows.get((1, 321))
    assert stored is not None
    assert stored.role == "bot"
    assert stored.text == "ответ"
    assert stored.connection_id == "bc1"


async def test_send_exception_no_bot_row() -> None:
    class RaisingBot(DummyBot):
        async def send_message(self, *args, **kwargs):
            raise RuntimeError("telegram error")

    bot = RaisingBot()
    repo = FakeMessageRepo()
    sender = TelegramBusinessSender(bot, repo)
    with pytest.raises(RuntimeError):
        await sender.send(incoming(), "ответ", 0)
    assert repo.rows == {}
