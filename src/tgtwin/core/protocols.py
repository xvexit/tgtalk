from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import (
    ChatMessage,
    Context,
    HistoryItem,
    IncomingMessage,
    ReplyLogEntry,
    StoredMessage,
)


class Step(Protocol):
    async def handle(self, ctx: Context) -> None: ...


class LLMProvider(Protocol):
    async def generate(self, system: str, messages: list[ChatMessage]) -> str: ...


class Sender(Protocol):  # реализация: Telegram; в тестах и dry-run: заглушка
    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None: ...

    async def notify_owner(self, connection_id: str, text: str) -> None: ...


class MessageRepository(Protocol):  # реализация: storage/repositories.py (Postgres); тесты: in-memory
    # add идемпотентен: повторная вставка того же (chat_id, message_id) не ошибка и не дубль
    async def add(self, msg: StoredMessage) -> None: ...

    async def exists(self, chat_id: int, message_id: int) -> bool: ...

    # last возвращает от старых к новым
    async def last(self, chat_id: int, n: int) -> list[HistoryItem]: ...

    async def last_owner_ts(self, chat_id: int) -> datetime | None: ...

    async def role_of(self, chat_id: int, message_id: int) -> str | None: ...


class ReplyLogRepository(Protocol):  # реализация: storage/repositories.py (Postgres); тесты: in-memory
    # add возвращает id записи (для mark_sent после реальной отправки)
    async def add(self, entry: ReplyLogEntry) -> int: ...

    async def mark_sent(self, log_id: int, sent: bool) -> None: ...

    # число реально отправленных ответов в чате с момента since
    async def count_sent_since(self, chat_id: int, since: datetime) -> int: ...


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
