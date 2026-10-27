from __future__ import annotations

import asyncio
import logging
from time import monotonic as _clock

from aiogram import Router
from aiogram.types import Message

from tgtwin.adapters.telegram.converter import aiogram_message_to_incoming
from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.core.models import Action, Context
from tgtwin.core.pipeline import Pipeline
from tgtwin.core.protocols import ReplyLogRepository, Sender

logger = logging.getLogger(__name__)
router = Router()

RATE_LIMIT_NOTIFY_INTERVAL = 3600.0


def setup(
    bot,
    pipeline: Pipeline,
    resolver: OwnerResolver,
    sender: Sender,
    log_repo: ReplyLogRepository,
) -> Router:
    locks: dict[int, asyncio.Lock] = {}
    rate_limit_notified: dict[int, float] = {}

    @router.business_message()
    async def handle(msg: Message) -> None:
        bc_id = msg.business_connection_id or ""
        info = await resolver.get(bc_id)
        from_owner = bool(info.owner_id and msg.from_user and msg.from_user.id == info.owner_id)
        incoming = aiogram_message_to_incoming(msg, bc_id, from_owner)
        if incoming is None:
            return
        lock = locks.setdefault(incoming.chat_id, asyncio.Lock())
        async with lock:
            ctx = Context(msg=incoming)
            await pipeline.run(ctx)
            if ctx.action == Action.ESCALATE:
                name = incoming.sender_name or "собеседник"
                await sender.notify_owner(bc_id, f"тут нужен ты: {name}")
            if ctx.meta.get("stopped_by") == "GuardRateLimitStep":
                name = incoming.sender_name or "собеседник"
                last = rate_limit_notified.get(incoming.chat_id, 0.0)
                now = _clock()
                if now - last >= RATE_LIMIT_NOTIFY_INTERVAL:
                    rate_limit_notified[incoming.chat_id] = now
                    await sender.notify_owner(bc_id, f"лимит ответов исчерпан: {name}")
            mode = ctx.cfg.mode.value if ctx.cfg else "off"
            if ctx.reply and not ctx.stop and mode != "off":
                parts = ctx.meta.get("replies")
                if not isinstance(parts, list) or not parts:
                    parts = [ctx.reply]
                parts = [str(part) for part in parts]
                delays = ctx.meta.get("delays")
                if not isinstance(delays, list) or len(delays) != len(parts):
                    delays = [float(ctx.meta.get("delay", 0.0))] * len(parts)
                for index, (part, delay) in enumerate(zip(parts, delays, strict=True)):
                    try:
                        sent_id = await sender.send(ctx.msg, part, delay)
                    except Exception:
                        logger.exception(
                            "send_failed",
                            extra={
                                "chat_id": ctx.msg.chat_id,
                                "message_id": ctx.msg.message_id,
                                "reply_index": index,
                                "reply_count": len(parts),
                            },
                        )
                        break
                    if index == 0 and sent_id is not None:
                        log_id = ctx.meta.get("reply_log_id")
                        if log_id is not None:
                            await log_repo.mark_sent(log_id, True)

    return router
