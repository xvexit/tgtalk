from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from tgtwin.adapters.telegram.converter import aiogram_message_to_incoming
from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.adapters.telegram.sender import DryRunSender
from tgtwin.core.models import Action, Context
from tgtwin.core.pipeline import Pipeline

router = Router()


def setup(bot, pipeline: Pipeline, resolver: OwnerResolver, sender: DryRunSender) -> Router:
    @router.business_message()
    async def handle(msg: Message) -> None:
        bc_id = msg.business_connection_id or ""
        info = await resolver.get(bc_id)
        from_owner = bool(info.owner_id and msg.from_user and msg.from_user.id == info.owner_id)
        incoming = aiogram_message_to_incoming(msg, bc_id, from_owner)
        if incoming is None:
            return
        ctx = Context(msg=incoming)
        await pipeline.run(ctx)
        mode = ctx.cfg.mode.value if ctx.cfg else "dry_run"
        if ctx.reply and not ctx.stop and mode != "off":
            await sender.send(ctx.msg, ctx.reply, getattr(ctx, "delay", 0.0))
        if ctx.action == Action.ESCALATE:
            await sender.notify_owner(bc_id, "Эскалация")
    return router
