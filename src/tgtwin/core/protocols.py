from __future__ import annotations

from datetime import datetime
from typing import Protocol

from .models import ChatMessage, Context, HistoryItem, IncomingMessage, StoredMessage


class Step(Protocol):
    async def handle(self, ctx: Context) -> None: ...


class LLMProvider(Protocol):
    async def generate(self, system: str, messages: list[ChatMessage]) -> str: ...


class Sender(Protocol):  # реализация: Telegram; в тестах и dry-run: заглушка
    async def send(self, msg: IncomingMessage, text: str, delay: float) -> int | None: ...

    async def notify_owner(self, connection_id: str, text: str) -> None: ...


class MessageRepository(Protocol):  # реализация: storage/repositories.py (Postgres); тесты: in-memory
    async def add(self, msg: StoredMessage) -> None: ...

    async def exists(self, chat_id: int, message_id: int) -> bool: ...

    async def last(self, chat_id: int, n: int) -> list[HistoryItem]: ...

    async def last_owner_ts(self, chat_id: int) -> datetime | None: ...


class Embedder(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
