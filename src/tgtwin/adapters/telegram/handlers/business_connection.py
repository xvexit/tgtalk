from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import BusinessConnection

from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.core.protocols import Sender

logger = logging.getLogger(__name__)
router = Router()


def setup(bot, sender: Sender, resolver: OwnerResolver) -> Router:
    @router.business_connection()
    async def handle(bc: BusinessConnection) -> None:
        if bc.id:
            owner_id = getattr(bc.user, "id", None) if getattr(bc, "user", None) else None
            user_chat_id = getattr(bc, "user_chat_id", None)
            resolver.set(bc.id, owner_id, user_chat_id)
            if not bc.is_enabled:
                try:
                    await sender.notify_owner(bc.id, "подключение отключено, проверь Premium")
                except Exception:
                    logger.exception("notify_on_disable_failed")
            else:
                try:
                    await sender.notify_owner(bc.id, "подключение включено")
                except Exception:
                    logger.exception("notify_on_enable_failed")
    return router
