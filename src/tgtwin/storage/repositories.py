from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from tgtwin.core.models import HistoryItem, StoredMessage
from tgtwin.core.protocols import MessageRepository
from tgtwin.storage.models import Message


class PostgresMessageRepository(MessageRepository):
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self.sessionmaker = sessionmaker

    async def add(self, msg: StoredMessage) -> None:
        async with self.sessionmaker() as session:
            stmt = insert(Message).values(
                chat_id=msg.chat_id,
                tg_message_id=msg.message_id,
                role=msg.role,
                text=msg.text,
                ts=msg.ts,
                connection_id=msg.connection_id,
            )
            stmt = stmt.on_conflict_do_nothing(index_elements=["chat_id", "tg_message_id"])
            await session.execute(stmt)
            await session.commit()

    async def exists(self, chat_id: int, message_id: int) -> bool:
        async with self.sessionmaker() as session:
            stmt = select(Message.id).where(Message.chat_id == chat_id, Message.tg_message_id == message_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none() is not None

    async def last(self, chat_id: int, n: int) -> list[HistoryItem]:
        async with self.sessionmaker() as session:
            subq = (
                select(Message.role, Message.text, Message.ts)
                .where(Message.chat_id == chat_id)
                .order_by(Message.ts.desc())
                .limit(n)
                .subquery()
            )
            stmt = select(subq.c.role, subq.c.text, subq.c.ts).order_by(subq.c.ts.asc())
            result = await session.execute(stmt)
            rows = result.all()
            items: list[HistoryItem] = []
            for role, text, ts in rows:
                items.append(HistoryItem(role=role, text=text or "", ts=ts))
            return items

    async def last_owner_ts(self, chat_id: int) -> datetime | None:
        async with self.sessionmaker() as session:
            stmt = select(func.max(Message.ts)).where(Message.chat_id == chat_id, Message.role == "owner")
            result = await session.execute(stmt)
            return result.scalar_one_or_none()
