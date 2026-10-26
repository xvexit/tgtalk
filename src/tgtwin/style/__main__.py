from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from tgtwin.config import Settings
from tgtwin.storage.db import get_engine
from tgtwin.storage.models import Message
from tgtwin.style.report import render_report
from tgtwin.style.stats import StyleMessage, build_style_stats


async def _load_messages(chat_id: int | None) -> list[StyleMessage]:
    settings = Settings()
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL не задан")
    engine = get_engine(settings.DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    stmt = (
        select(Message.chat_id, Message.tg_message_id, Message.role, Message.text, Message.ts)
        .where(Message.text.is_not(None))
        .order_by(Message.chat_id, Message.ts, Message.tg_message_id)
    )
    if chat_id is not None:
        stmt = stmt.where(Message.chat_id == chat_id)
    try:
        async with sessionmaker() as session:
            rows = (await session.execute(stmt)).all()
    finally:
        await engine.dispose()

    messages: list[StyleMessage] = []
    for row_chat_id, message_id, role, text, ts in rows:
        if text and text.strip():
            messages.append(
                StyleMessage(
                    chat_id=row_chat_id,
                    message_id=message_id,
                    role=role,
                    text=text,
                    ts=ts,
                )
            )
    return messages


async def _run(chat_id: int | None, out: Path) -> tuple[int, int, int, int]:
    messages = await _load_messages(chat_id)
    stats = build_style_stats(messages)
    scope = f"чат {chat_id}" if chat_id is not None else "все чаты"
    report = render_report(stats, scope=scope, generated_at=datetime.now(UTC))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    return stats.message_count, stats.owner_count, stats.them_count, stats.chat_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tgtwin.style")
    parser.add_argument("--chat", type=int, default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    out = Path(args.out)
    total, owner, them, chats = asyncio.run(_run(args.chat, out))
    print(f"report: {out}")
    print(f"messages: {total}, mine: {owner}, them: {them}, chats: {chats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
