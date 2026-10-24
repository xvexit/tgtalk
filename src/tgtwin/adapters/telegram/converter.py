from __future__ import annotations

from aiogram.types import Message

from tgtwin.core.models import IncomingMessage


def aiogram_message_to_incoming(msg: Message, connection_id: str, from_owner: bool) -> IncomingMessage | None:
    if not msg.text:
        return None
    return IncomingMessage(
        channel="telegram",
        connection_id=connection_id,
        chat_id=msg.chat.id,
        message_id=msg.message_id,
        text=msg.text,
        from_owner=from_owner,
        ts=msg.date,
    )
