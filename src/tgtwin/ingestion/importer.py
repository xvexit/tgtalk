from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Protocol

from tgtwin.ingestion.models import ParsedChat, ParsedExport

ImportRow = tuple[int, str, str, datetime]


class IngestionStore(Protocol):
    async def find_import(self, file_hash: str, chats: Sequence[int]) -> int | None: ...

    async def add_import(
        self,
        file_hash: str,
        filename: str,
        chats: Sequence[int],
        stats: dict[str, Any],
    ) -> None: ...

    async def earliest_live_ts(self, chat_id: int) -> datetime | None: ...

    async def add_imported_messages(
        self,
        chat_id: int,
        rows: Sequence[ImportRow],
    ) -> int: ...

    async def upsert_contact(self, chat_id: int, display_name: str) -> None: ...


@dataclass(frozen=True)
class ChatImportStats:
    chat_id: int
    name: str
    parsed: int
    skipped_live: int
    inserted: int
    conflicts: int
    service: int
    forwarded: int
    empty: int
    malformed: int


@dataclass(frozen=True)
class ImportReport:
    file_hash: str
    filename: str
    chats: list[int]
    already_imported: bool
    chat_stats: list[ChatImportStats]


def chunked[T](items: Sequence[T], size: int) -> list[list[T]]:
    if size <= 0:
        raise ValueError("size должен быть больше нуля")
    return [list(items[index : index + size]) for index in range(0, len(items), size)]


async def import_chats(
    store: IngestionStore,
    parsed: ParsedExport,
    chat_ids: Sequence[int],
    *,
    file_hash: str,
    filename: str,
    batch_size: int = 1000,
) -> ImportReport:
    selected = sorted(set(chat_ids))
    chat_map: dict[int, ParsedChat] = {chat.chat_id: chat for chat in parsed.chats}
    missing = [chat_id for chat_id in selected if chat_id not in chat_map]
    if missing:
        missing_text = ", ".join(str(chat_id) for chat_id in missing)
        raise ValueError(f"чаты не найдены в экспорте: {missing_text}")

    existing = await store.find_import(file_hash, selected)
    if existing is not None:
        return ImportReport(
            file_hash=file_hash,
            filename=filename,
            chats=selected,
            already_imported=True,
            chat_stats=[],
        )

    chat_stats: list[ChatImportStats] = []
    for chat_id in selected:
        chat = chat_map[chat_id]
        earliest_live = await store.earliest_live_ts(chat_id)
        eligible = [
            message
            for message in chat.messages
            if earliest_live is None or message.ts < earliest_live
        ]
        skipped_live = len(chat.messages) - len(eligible)
        inserted = 0
        conflicts = 0
        for batch in chunked(eligible, batch_size):
            rows: list[ImportRow] = [
                (message.message_id, message.role, message.text, message.ts)
                for message in batch
            ]
            batch_inserted = await store.add_imported_messages(chat_id, rows)
            inserted += batch_inserted
            conflicts += len(batch) - batch_inserted

        await store.upsert_contact(chat_id, chat.name)
        chat_stats.append(
            ChatImportStats(
                chat_id=chat_id,
                name=chat.name,
                parsed=len(chat.messages),
                skipped_live=skipped_live,
                inserted=inserted,
                conflicts=conflicts,
                service=chat.stats.service,
                forwarded=chat.stats.forwarded,
                empty=chat.stats.empty,
                malformed=chat.stats.malformed,
            )
        )

    stats = {
        "chats": [asdict(item) for item in chat_stats],
        "totals": {
            "parsed": sum(item.parsed for item in chat_stats),
            "skipped_live": sum(item.skipped_live for item in chat_stats),
            "inserted": sum(item.inserted for item in chat_stats),
            "conflicts": sum(item.conflicts for item in chat_stats),
            "service": sum(item.service for item in chat_stats),
            "forwarded": sum(item.forwarded for item in chat_stats),
            "empty": sum(item.empty for item in chat_stats),
            "malformed": sum(item.malformed for item in chat_stats),
        },
    }
    await store.add_import(file_hash, filename, selected, stats)

    return ImportReport(
        file_hash=file_hash,
        filename=filename,
        chats=selected,
        already_imported=False,
        chat_stats=chat_stats,
    )
