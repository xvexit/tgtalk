from __future__ import annotations

from datetime import UTC, datetime

from aiogram.types import Chat, Message, User

from tgtwin.adapters.telegram.converter import aiogram_message_to_incoming


def test_converter_business_message() -> None:
    user = User(id=1, is_bot=False, first_name="x")
    chat = Chat(id=123, type="private")
    msg = Message(message_id=10, date=datetime.now(UTC), chat=chat, from_user=user, text="hi")
    res = aiogram_message_to_incoming(msg, "bc1", False)
    assert res is not None
    assert res.chat_id == 123
    assert res.message_id == 10
    assert res.from_owner is False
