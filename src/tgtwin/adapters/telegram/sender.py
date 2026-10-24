from __future__ import annotations

import logging

from aiogram import Bot

from tgtwin.core.models import IncomingMessage
from tgtwin.core.protocols import Sender

logger = logging.getLogger(__name__)


class DryRunSender(Sender):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot

    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None:
        logger.info("ответил бы", extra={"chat_id": msg.chat_id, "message_id": msg.message_id})
        return None

    async def notify_owner(self, connection_id: str, text: str) -> None:
        try:
            await self.bot.send_message(chat_id=connection_id, text=text)
        except Exception:
            logger.exception("notify_owner_failed")
