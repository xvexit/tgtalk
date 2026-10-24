from __future__ import annotations

from aiogram import Router
from aiogram.types import Message

from tgtwin.adapters.telegram.converter import aiogram_message_to_incoming
from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.core.models import Context
from tgtwin.core.pipeline import Pipeline

router = Router()


def setup(bot, pipeline: Pipeline, resolver: OwnerResolver) -> Router:
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
    return router
