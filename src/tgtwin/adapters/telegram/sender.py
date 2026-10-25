from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from aiogram import Bot

from tgtwin.core.models import IncomingMessage, StoredMessage
from tgtwin.core.protocols import MessageRepository, Sender

logger = logging.getLogger(__name__)


class BaseSender(Sender):
    def __init__(self, bot: Bot, resolver: Any | None = None) -> None:
        self.bot = bot
        self.resolver = resolver

    def set_resolver(self, resolver: Any) -> None:
        self.resolver = resolver

    async def notify_owner(self, connection_id: str, text: str) -> None:
        try:
            user_chat_id = None
            if self.resolver is not None:
                info = getattr(self.resolver, "_cache", {}).get(connection_id)
                if info is not None:
                    user_chat_id = getattr(info, "user_chat_id", None)
            if user_chat_id is None:
                logger.warning("notify_owner_no_chat_id", extra={"connection_id": connection_id})
                return
            await self.bot.send_message(chat_id=user_chat_id, text=text)
        except Exception:
            logger.exception("notify_owner_failed")


class DryRunSender(BaseSender):
    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None:
        mode = "dry_run"
        reply_len = len(text) if text else 0
        logger.info(
            f"event=would_reply chat_id={msg.chat_id} message_id={msg.message_id} mode={mode} reply_len={reply_len}"
        )
        return None


class TelegramBusinessSender(BaseSender):
    def __init__(self, bot: Bot, repo: MessageRepository, resolver: Any | None = None) -> None:
        super().__init__(bot, resolver)
        self.repo = repo

    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None:
        await self.bot.send_chat_action(
            chat_id=msg.chat_id,
            action="typing",
            business_connection_id=msg.connection_id,
        )
        if delay > 0:
            await asyncio.sleep(delay)
        sent = await self.bot.send_message(
            chat_id=msg.chat_id,
            text=text,
            business_connection_id=msg.connection_id,
        )
        message_id = getattr(sent, "message_id", None)
        if message_id is not None:
            await self.repo.add(
                StoredMessage(
                    chat_id=msg.chat_id,
                    message_id=message_id,
                    role="bot",
                    text=text,
                    ts=datetime.now(UTC),
                    connection_id=msg.connection_id,
                )
            )
        return message_id
