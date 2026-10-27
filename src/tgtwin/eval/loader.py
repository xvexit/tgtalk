from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from tgtwin.config import Settings
from tgtwin.eval.models import EvalMessage
from tgtwin.storage.db import get_engine
from tgtwin.storage.models import Message


async def load_messages(chat_ids: Sequence[int]) -> dict[int, list[EvalMessage]]:
    settings = Settings()
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL не задан")
    engine = get_engine(settings.DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    stmt = (
        select(Message.chat_id, Message.tg_message_id, Message.role, Message.text, Message.ts)
        .where(Message.chat_id.in_(list(chat_ids)), Message.text.is_not(None))
        .order_by(Message.chat_id, Message.ts, Message.tg_message_id)
    )
    try:
        async with sessionmaker() as session:
            rows = (await session.execute(stmt)).all()
    finally:
        await engine.dispose()

    result: dict[int, list[EvalMessage]] = {chat_id: [] for chat_id in chat_ids}
    for chat_id, message_id, role, text, ts in rows:
        if not text or not text.strip():
            continue
        result.setdefault(chat_id, []).append(
            EvalMessage(
                chat_id=chat_id,
                message_id=message_id,
                role=role,
                text=text,
                ts=_aware(ts),
            )
        )
    return result


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
