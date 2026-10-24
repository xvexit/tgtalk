from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tgtwin.core.models import HistoryItem, StoredMessage
from tgtwin.core.protocols import MessageRepository
from tgtwin.storage.models import Message


class PostgresMessageRepository(MessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, msg: StoredMessage) -> None:
        stmt = select(Message).where(Message.chat_id == msg.chat_id, Message.tg_message_id == msg.message_id)
        result = await self.session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            return
        row = Message(
            chat_id=msg.chat_id,
            tg_message_id=msg.message_id,
            role=msg.role,
            text=msg.text,
            ts=msg.ts,
            connection_id=msg.connection_id,
        )
        self.session.add(row)
        await self.session.commit()

    async def exists(self, chat_id: int, message_id: int) -> bool:
        stmt = select(Message.id).where(Message.chat_id == chat_id, Message.tg_message_id == message_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def last(self, chat_id: int, n: int) -> list[HistoryItem]:
        subq = (
            select(Message)
            .where(Message.chat_id == chat_id)
            .order_by(Message.ts.desc())
            .limit(n)
            .subquery()
        )
        stmt = select(Message).from_statement(select(subq.c.role, subq.c.text, subq.c.ts).order_by(subq.c.ts.asc()))
        result = await self.session.execute(stmt)
        rows = result.all()
        items: list[HistoryItem] = []
        for role, text, ts in rows:
            items.append(HistoryItem(role=role, text=text or "", ts=ts))
        return items

    async def last_owner_ts(self, chat_id: int) -> datetime | None:
        stmt = select(func.max(Message.ts)).where(Message.chat_id == chat_id, Message.role == "owner")
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
