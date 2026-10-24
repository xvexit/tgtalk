from __future__ import annotations

from aiogram import Dispatcher


def setup_dispatcher(dp: Dispatcher, *routers) -> Dispatcher:
    for r in routers:
        dp.include_router(r)
    return dp


ALLOWED_UPDATES = [
    "message",
    "business_connection",
    "business_message",
    "edited_business_message",
    "deleted_business_messages",
]
