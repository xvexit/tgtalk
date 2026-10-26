from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, select

from tgtwin.core.models import StoredMessage
from tgtwin.ingestion.importer import import_chats
from tgtwin.ingestion.models import ParsedChat, ParsedExport, ParsedMessage
from tgtwin.storage.db import get_sessionmaker
from tgtwin.storage.models import Contact, Import, Message
from tgtwin.storage.repositories import PostgresIngestionRepository, PostgresMessageRepository

CHAT_ID = 990000001
CHAT_ID_2 = 990000002
FILE_HASH = "test-ingestion-integration-hash"


def _msg(message_id: int, role: str, text: str, ts: datetime) -> ParsedMessage:
    return ParsedMessage(
        message_id=message_id,
        role=role,  # type: ignore[arg-type]
        text=text,
        ts=ts,
    )


async def _cleanup(sessionmaker) -> None:
    async with sessionmaker() as session:
        await session.execute(delete(Import).where(Import.file_hash == FILE_HASH))
        await session.execute(delete(Message).where(Message.chat_id.in_([CHAT_ID, CHAT_ID_2])))
        await session.execute(delete(Contact).where(Contact.chat_id.in_([CHAT_ID, CHAT_ID_2])))
        await session.commit()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_import_integration() -> None:
    url = os.environ.get("DATABASE_URL", "")
    sessionmaker = get_sessionmaker(url)
    store = PostgresIngestionRepository(sessionmaker)
    message_repo = PostgresMessageRepository(sessionmaker)
    now = datetime.now(UTC)

    await _cleanup(sessionmaker)
    try:
        await message_repo.add(
            StoredMessage(
                chat_id=CHAT_ID,
                message_id=100,
                role="them",
                text="live",
                ts=now,
            )
        )
        async with sessionmaker() as session:
            session.add(
                Contact(
                    chat_id=CHAT_ID,
                    display_name="old",
                    mode="auto",
                    overrides={"keep": True},
                )
            )
            await session.commit()

        chat = ParsedChat(
            chat_id=CHAT_ID,
            name="new",
            raw_message_count=4,
            messages=[
                _msg(98, "owner", "old-1", now - timedelta(seconds=2)),
                _msg(99, "them", "old-2", now - timedelta(seconds=1)),
                _msg(100, "them", "live", now),
                _msg(101, "them", "newer", now + timedelta(seconds=1)),
            ],
        )
        parsed = ParsedExport(format="full", owner_id=1, chats=[chat])

        report = await import_chats(
            store,
            parsed,
            [CHAT_ID],
            file_hash=FILE_HASH,
            filename="result.json",
        )

        assert report.already_imported is False
        assert report.chat_stats[0].inserted == 2
        assert report.chat_stats[0].skipped_live == 2

        async with sessionmaker() as session:
            rows = (
                await session.execute(
                    select(Message.tg_message_id, Message.source)
                    .where(Message.chat_id == CHAT_ID)
                    .order_by(Message.tg_message_id)
                )
            ).all()
            assert rows == [(98, "import"), (99, "import"), (100, "live")]

            contact = await session.get(Contact, CHAT_ID)
            assert contact is not None
            assert contact.display_name == "new"
            assert contact.mode == "auto"
            assert contact.overrides == {"keep": True}

            imports = (
                await session.execute(select(Import).where(Import.file_hash == FILE_HASH))
            ).scalars().all()
            assert len(imports) == 1
            assert imports[0].chats == [CHAT_ID]
            assert imports[0].stats["totals"]["inserted"] == 2

        again = await import_chats(
            store,
            parsed,
            [CHAT_ID],
            file_hash=FILE_HASH,
            filename="result.json",
        )
        assert again.already_imported is True

        chat_2 = ParsedChat(
            chat_id=CHAT_ID_2,
            name="second",
            raw_message_count=1,
            messages=[_msg(1, "owner", "second", now - timedelta(days=1))],
        )
        parsed_both = ParsedExport(format="full", owner_id=1, chats=[chat, chat_2])
        second_run = await import_chats(
            store,
            parsed_both,
            [CHAT_ID, CHAT_ID_2],
            file_hash=FILE_HASH,
            filename="result.json",
        )

        assert second_run.already_imported is False
        async with sessionmaker() as session:
            imports = (
                await session.execute(select(Import).where(Import.file_hash == FILE_HASH))
            ).scalars().all()
            assert len(imports) == 2
            chat_2_rows = (
                await session.execute(
                    select(Message.tg_message_id, Message.source).where(
                        Message.chat_id == CHAT_ID_2
                    )
                )
            ).all()
            assert chat_2_rows == [(1, "import")]
    finally:
        await _cleanup(sessionmaker)
