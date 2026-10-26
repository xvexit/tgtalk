from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import async_sessionmaker

from tgtwin.core.models import HistoryItem, ReplyLogEntry, StoredMessage
from tgtwin.core.protocols import MessageRepository, ReplyLogRepository
from tgtwin.storage.models import Contact, Import, Message, ReplyLog


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
                select(Message.tg_message_id, Message.role, Message.text, Message.ts)
                .where(Message.chat_id == chat_id)
                .order_by(Message.ts.desc())
                .limit(n)
                .subquery()
            )
            stmt = select(subq.c.tg_message_id, subq.c.role, subq.c.text, subq.c.ts).order_by(subq.c.ts.asc())
            result = await session.execute(stmt)
            rows = result.all()
            items: list[HistoryItem] = []
            for tg_message_id, role, text, ts in rows:
                items.append(HistoryItem(message_id=tg_message_id, role=role, text=text or "", ts=ts))
            return items

    async def last_owner_ts(self, chat_id: int) -> datetime | None:
        async with self.sessionmaker() as session:
            stmt = select(func.max(Message.ts)).where(Message.chat_id == chat_id, Message.role == "owner")
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def role_of(self, chat_id: int, message_id: int) -> str | None:
        async with self.sessionmaker() as session:
            stmt = select(Message.role).where(
                Message.chat_id == chat_id, Message.tg_message_id == message_id
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()


class PostgresIngestionRepository:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self.sessionmaker = sessionmaker

    async def find_import(self, file_hash: str, chats: Sequence[int]) -> int | None:
        async with self.sessionmaker() as session:
            stmt = select(Import.id).where(
                Import.file_hash == file_hash,
                Import.chats == list(chats),
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def add_import(
        self,
        file_hash: str,
        filename: str,
        chats: Sequence[int],
        stats: dict[str, Any],
    ) -> None:
        async with self.sessionmaker() as session:
            stmt = (
                insert(Import)
                .values(
                    file_hash=file_hash,
                    filename=filename,
                    chats=list(chats),
                    stats=stats,
                )
                .on_conflict_do_nothing(index_elements=["file_hash", "chats"])
            )
            await session.execute(stmt)
            await session.commit()

    async def earliest_live_ts(self, chat_id: int) -> datetime | None:
        async with self.sessionmaker() as session:
            stmt = select(func.min(Message.ts)).where(
                Message.chat_id == chat_id,
                Message.source == "live",
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def add_imported_messages(
        self,
        chat_id: int,
        rows: Sequence[tuple[int, str, str, datetime]],
    ) -> int:
        if not rows:
            return 0
        values = [
            {
                "chat_id": chat_id,
                "tg_message_id": message_id,
                "role": role,
                "text": text,
                "ts": ts,
                "source": "import",
            }
            for message_id, role, text, ts in rows
        ]
        async with self.sessionmaker() as session:
            stmt = (
                insert(Message)
                .values(values)
                .on_conflict_do_nothing(index_elements=["chat_id", "tg_message_id"])
                .returning(Message.id)
            )
            result = await session.execute(stmt)
            inserted = len(result.all())
            await session.commit()
            return inserted

    async def upsert_contact(self, chat_id: int, display_name: str) -> None:
        async with self.sessionmaker() as session:
            stmt = insert(Contact).values(chat_id=chat_id, display_name=display_name)
            if display_name:
                stmt = stmt.on_conflict_do_update(
                    index_elements=["chat_id"],
                    set_={"display_name": stmt.excluded.display_name},
                )
            else:
                stmt = stmt.on_conflict_do_nothing(index_elements=["chat_id"])
            await session.execute(stmt)
            await session.commit()


class PostgresReplyLogRepository(ReplyLogRepository):
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self.sessionmaker = sessionmaker

    async def add(self, entry: ReplyLogEntry) -> int:
        async with self.sessionmaker() as session:
            stmt = (
                insert(ReplyLog)
                .values(
                    chat_id=entry.chat_id,
                    trigger_message_id=entry.trigger_message_id,
                    mode=entry.mode,
                    reply=entry.reply,
                    context=entry.context,
                    sent=entry.sent,
                    ts=entry.ts or datetime.now(UTC),
                )
                .returning(ReplyLog.id)
            )
            result = await session.execute(stmt)
            log_id = result.scalar_one()
            await session.commit()
            return log_id

    async def mark_sent(self, log_id: int, sent: bool) -> None:
        async with self.sessionmaker() as session:
            stmt = update(ReplyLog).where(ReplyLog.id == log_id).values(sent=sent)
            await session.execute(stmt)
            await session.commit()

    async def count_sent_since(self, chat_id: int, since: datetime) -> int:
        async with self.sessionmaker() as session:
            stmt = select(func.count()).where(
                ReplyLog.chat_id == chat_id,
                ReplyLog.sent.is_(True),
                ReplyLog.ts >= since,
            )
            result = await session.execute(stmt)
            return int(result.scalar_one())
