from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import BusinessConnection

from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.adapters.telegram.sender import DryRunSender

logger = logging.getLogger(__name__)
router = Router()


def setup(bot, sender: DryRunSender, resolver: OwnerResolver) -> Router:
    @router.business_connection()
    async def handle(bc: BusinessConnection) -> None:
        if bc.id:
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
