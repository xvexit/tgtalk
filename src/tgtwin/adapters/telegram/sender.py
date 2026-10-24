from __future__ import annotations

import logging

from aiogram import Bot

from tgtwin.core.models import IncomingMessage
from tgtwin.core.protocols import Sender

logger = logging.getLogger(__name__)


class DryRunSender(Sender):
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self.resolver = None

    def set_resolver(self, resolver) -> None:
        self.resolver = resolver

    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None:
        mode = "dry_run"
        reply_len = len(text) if text else 0
        logger.info(
            f"event=would_reply chat_id={msg.chat_id} message_id={msg.message_id} mode={mode} reply_len={reply_len}"
        )
        return None

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
