from __future__ import annotations

import argparse
import asyncio
import hashlib
import sys
from datetime import UTC
from pathlib import Path

from sqlalchemy.ext.asyncio import async_sessionmaker

from tgtwin.config import Settings
from tgtwin.ingestion.importer import ImportReport, import_chats
from tgtwin.ingestion.models import ParsedChat
from tgtwin.ingestion.parser import OwnerIdError, parse_export
from tgtwin.storage.db import get_engine
from tgtwin.storage.repositories import PostgresIngestionRepository


def sha256_file(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _counts(chat: ParsedChat) -> tuple[int, int]:
    owner_count = sum(1 for message in chat.messages if message.role == "owner")
    them_count = sum(1 for message in chat.messages if message.role == "them")
    return owner_count, them_count


def _dates(chat: ParsedChat) -> tuple[str, str]:
    if not chat.messages:
        return "—", "—"
    start = chat.messages[0].ts.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
    end = chat.messages[-1].ts.astimezone(UTC).strftime("%Y-%m-%d %H:%M:%S")
    return start, end


def _cmd_list(
    path: Path,
    owner_id: int | None,
    sort_by: str,
    min_mine: int,
    limit: int,
    names: bool,
) -> int:
    parsed = parse_export(path, owner_id)
    rows: list[tuple[ParsedChat, int, int, float]] = []
    for chat in parsed.chats:
        owner_count, them_count = _counts(chat)
        if owner_count < min_mine:
            continue
        last_ts = chat.messages[-1].ts.timestamp() if chat.messages else 0.0
        rows.append((chat, owner_count, them_count, last_ts))

    if sort_by == "mine":
        rows.sort(key=lambda row: (-row[1], row[0].chat_id))
    elif sort_by == "total":
        rows.sort(key=lambda row: (-(row[1] + row[2]), row[0].chat_id))
    else:
        rows.sort(key=lambda row: (-row[3], row[0].chat_id))
    if limit > 0:
        rows = rows[:limit]

    print(f"format: {parsed.format}")
    print(f"owner_id: {parsed.owner_id}")
    print(f"chats: {len(rows)} shown / {len(parsed.chats)} total")
    header = (
        f"{'chat_id':>12}  {'моих':>5}  {'их':>4}  {'всего':>5}  "
        f"{'первая':<19}  {'последняя':<19}"
    )
    if names:
        header += "  имя"
    print(header)
    for chat, owner_count, them_count, _ in rows:
        first, last = _dates(chat)
        line = (
            f"{chat.chat_id:>12}  {owner_count:>5}  {them_count:>4}  "
            f"{owner_count + them_count:>5}  {first:<19}  {last:<19}"
        )
        if names:
            line += f"  {' '.join(chat.name.split())}"
        print(line)
    print(
        "skipped: "
        f"service={sum(chat.stats.service for chat in parsed.chats)}, "
        f"forwarded={sum(chat.stats.forwarded for chat in parsed.chats)}, "
        f"empty={sum(chat.stats.empty for chat in parsed.chats)}, "
        f"malformed={sum(chat.stats.malformed for chat in parsed.chats)}"
    )
    return 0


def _print_report(report: ImportReport) -> None:
    print(f"file_hash: {report.file_hash}")
    print(f"filename: {report.filename}")
    print(f"chats: {', '.join(str(chat_id) for chat_id in report.chats)}")
    if report.already_imported:
        print("already imported: yes")
        return
    print("already imported: no")
    for stats in report.chat_stats:
        print(
            f"chat {stats.chat_id}: parsed={stats.parsed}, skipped_live={stats.skipped_live}, "
            f"inserted={stats.inserted}, conflicts={stats.conflicts}, "
            f"service={stats.service}, forwarded={stats.forwarded}, empty={stats.empty}, "
            f"malformed={stats.malformed}"
        )
    print(
        "totals: "
        f"inserted={sum(item.inserted for item in report.chat_stats)}, "
        f"conflicts={sum(item.conflicts for item in report.chat_stats)}, "
        f"skipped_live={sum(item.skipped_live for item in report.chat_stats)}"
    )


async def _run_import(path: Path, chat_ids: list[int], owner_id: int | None) -> int:
    settings = Settings()
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL не задан")
    file_hash = sha256_file(path)
    selected = sorted(set(chat_ids))
    engine = get_engine(settings.DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    store = PostgresIngestionRepository(sessionmaker)
    try:
        existing = await store.find_import(file_hash, selected)
        if existing is not None:
            _print_report(
                ImportReport(
                    file_hash=file_hash,
                    filename=path.name,
                    chats=selected,
                    already_imported=True,
                    chat_stats=[],
                )
            )
            return 0

        parsed = parse_export(path, owner_id)
        report = await import_chats(
            store,
            parsed,
            selected,
            file_hash=file_hash,
            filename=path.name,
        )
        _print_report(report)
        return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tgtwin.ingestion")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="показать личные диалоги из экспорта")
    list_parser.add_argument("file")
    list_parser.add_argument("--owner-id", type=int, default=None)
    list_parser.add_argument(
        "--sort",
        choices=("mine", "total", "last"),
        default="mine",
        help="сортировка: mine (по умолчанию), total, last",
    )
    list_parser.add_argument("--min-mine", type=int, default=0)
    list_parser.add_argument(
        "--limit",
        type=int,
        default=40,
        help="сколько строк показать; 0 — без ограничения",
    )
    list_parser.add_argument("--names", action="store_true", help="показать имена чатов")

    run_parser = subparsers.add_parser("run", help="импортировать выбранные диалоги")
    run_parser.add_argument("file")
    run_parser.add_argument("--chat", dest="chats", type=int, action="append", required=True)
    run_parser.add_argument("--owner-id", type=int, default=None)

    args = parser.parse_args(argv)
    path = Path(args.file)
    try:
        if args.command == "list":
            if args.min_mine < 0:
                raise ValueError("--min-mine должен быть >= 0")
            if args.limit < 0:
                raise ValueError("--limit должен быть >= 0")
            return _cmd_list(
                path,
                args.owner_id,
                args.sort,
                args.min_mine,
                args.limit,
                args.names,
            )
        return asyncio.run(_run_import(path, args.chats, args.owner_id))
    except (OwnerIdError, ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
