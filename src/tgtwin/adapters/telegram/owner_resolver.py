from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot


@dataclass
class OwnerInfo:
    owner_id: int | None
    user_chat_id: int | None


class OwnerResolver:
    def __init__(self, bot: Bot) -> None:
        self.bot = bot
        self._cache: dict[str, OwnerInfo] = {}

    async def get(self, connection_id: str) -> OwnerInfo:
        if connection_id in self._cache:
            return self._cache[connection_id]
        conn = await self.bot.get_business_connection(business_connection_id=connection_id)
        owner_id = conn.user.id if conn and conn.user else None
        info = OwnerInfo(owner_id=owner_id, user_chat_id=None)
        self._cache[connection_id] = info
        return info

    def set_user_chat(self, connection_id: str, user_chat_id: int) -> None:
        info = self._cache.get(connection_id) or OwnerInfo(owner_id=None, user_chat_id=None)
        info.user_chat_id = user_chat_id
        self._cache[connection_id] = info
