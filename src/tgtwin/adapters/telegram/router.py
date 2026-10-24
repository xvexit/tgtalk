from __future__ import annotations

from aiogram import Dispatcher


def setup_dispatcher(dp: Dispatcher, *routers) -> Dispatcher:
    for r in routers:
        dp.include_router(r)
    return dp


ALLOWED_UPDATES = [
    "business_connection",
    "business_message",
]
