from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from tgtwin.ingestion.importer import chunked, import_chats
from tgtwin.ingestion.models import ParsedChat, ParsedExport, ParsedMessage

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _msg(message_id: int, role: str, offset: int = 0, text: str | None = None) -> ParsedMessage:
    return ParsedMessage(
        message_id=message_id,
        role=role,  # type: ignore[arg-type]
        text=text or f"text-{message_id}",
        ts=T0 + timedelta(seconds=offset),
    )


def _chat(chat_id: int, messages: list[ParsedMessage]) -> ParsedChat:
    return ParsedChat(
        chat_id=chat_id,
        name=f"chat-{chat_id}",
        messages=messages,
        raw_message_count=len(messages),
    )


@dataclass
class FakeStore:
    existing: int | None = None
    live_ts: dict[int, datetime] = field(default_factory=dict)
    insert_return: int | None = None
    insert_calls: list[tuple[int, list[tuple[int, str, str, datetime]]]] = field(
        default_factory=list
    )
    contacts: list[tuple[int, str]] = field(default_factory=list)
    imports: list[tuple[str, str, list[int], dict[str, Any]]] = field(default_factory=list)

    async def find_import(self, file_hash: str, chats: list[int]) -> int | None:
        return self.existing

    async def add_import(
        self,
        file_hash: str,
        filename: str,
        chats: list[int],
        stats: dict[str, Any],
    ) -> None:
        self.imports.append((file_hash, filename, chats, stats))

    async def earliest_live_ts(self, chat_id: int) -> datetime | None:
        return self.live_ts.get(chat_id)

    async def add_imported_messages(
        self,
        chat_id: int,
        rows: list[tuple[int, str, str, datetime]],
    ) -> int:
        self.insert_calls.append((chat_id, rows))
        if self.insert_return is not None:
            return min(self.insert_return, len(rows))
        return len(rows)

    async def upsert_contact(self, chat_id: int, display_name: str) -> None:
        self.contacts.append((chat_id, display_name))


def _export(*chats: ParsedChat) -> ParsedExport:
    return ParsedExport(format="full", owner_id=111, chats=list(chats))


def test_chunked() -> None:
    assert chunked(list(range(5)), 2) == [[0, 1], [2, 3], [4]]
    assert chunked([], 1000) == []


@pytest.mark.asyncio
async def test_import_only_older_than_live() -> None:
    store = FakeStore(live_ts={1: T0 + timedelta(seconds=2)})
    messages = [_msg(1, "them", 0), _msg(2, "owner", 1), _msg(3, "them", 2), _msg(4, "owner", 3)]
    parsed = _export(_chat(1, messages))

    report = await import_chats(
        store, parsed, [1], file_hash="hash", filename="result.json"
    )

    rows = [row for _, batch in store.insert_calls for row in batch]
    assert [row[0] for row in rows] == [1, 2]
    assert report.already_imported is False
    assert report.chat_stats[0].skipped_live == 2
    assert report.chat_stats[0].inserted == 2


@pytest.mark.asyncio
async def test_import_uses_batches() -> None:
    store = FakeStore()
    messages = [_msg(i, "owner", i) for i in range(5)]
    parsed = _export(_chat(1, messages))

    await import_chats(
        store, parsed, [1], file_hash="hash", filename="result.json", batch_size=2
    )

    assert [len(batch) for _, batch in store.insert_calls] == [2, 2, 1]


@pytest.mark.asyncio
async def test_already_imported_skips_everything() -> None:
    store = FakeStore(existing=42)
    parsed = _export(_chat(1, [_msg(1, "owner")]))

    report = await import_chats(store, parsed, [1], file_hash="hash", filename="result.json")

    assert report.already_imported is True
    assert store.insert_calls == []
    assert store.contacts == []
    assert store.imports == []


@pytest.mark.asyncio
async def test_contact_and_import_record_are_written() -> None:
    store = FakeStore()
    parsed = _export(_chat(1, [_msg(1, "owner")]))

    report = await import_chats(
        store, parsed, [1, 1], file_hash="hash", filename="result.json"
    )

    assert store.contacts == [(1, "chat-1")]
    assert len(store.imports) == 1
    file_hash, filename, chats, stats = store.imports[0]
    assert file_hash == "hash"
    assert filename == "result.json"
    assert chats == [1]
    assert stats["totals"]["inserted"] == 1
    assert report.chats == [1]


@pytest.mark.asyncio
async def test_conflicts_are_counted() -> None:
    store = FakeStore(insert_return=0)
    parsed = _export(_chat(1, [_msg(1, "owner"), _msg(2, "owner", 1)]))

    report = await import_chats(
        store, parsed, [1], file_hash="hash", filename="result.json"
    )

    assert report.chat_stats[0].inserted == 0
    assert report.chat_stats[0].conflicts == 2


@pytest.mark.asyncio
async def test_unknown_chat_raises_before_writes() -> None:
    store = FakeStore()
    parsed = _export(_chat(1, [_msg(1, "owner")]))

    with pytest.raises(ValueError, match="999"):
        await import_chats(
            store, parsed, [999], file_hash="hash", filename="result.json"
        )

    assert store.insert_calls == []
    assert store.imports == []
