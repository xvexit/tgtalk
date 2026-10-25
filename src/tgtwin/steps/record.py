from __future__ import annotations

import logging

from tgtwin.core.models import Action, Context, StoredMessage
from tgtwin.core.protocols import MessageRepository

logger = logging.getLogger(__name__)


class RecordStep:
    def __init__(self, repo: MessageRepository) -> None:
        self.repo = repo

    async def handle(self, ctx: Context) -> None:
        if ctx.msg.from_owner:
            if await self.repo.exists(ctx.msg.chat_id, ctx.msg.message_id):
                role = await self.repo.role_of(ctx.msg.chat_id, ctx.msg.message_id)
                if role == "bot":
                    logger.warning(
                        "echo_of_bot_reply",
                        extra={"chat_id": ctx.msg.chat_id, "message_id": ctx.msg.message_id},
                    )
                ctx.stop = True
                return
        stored = StoredMessage(
            chat_id=ctx.msg.chat_id,
            message_id=ctx.msg.message_id,
            role="owner" if ctx.msg.from_owner else "them",
            text=ctx.msg.text,
            ts=ctx.msg.ts,
            connection_id=ctx.msg.connection_id,
        )
        await self.repo.add(stored)
        ctx.action = Action.NONE
