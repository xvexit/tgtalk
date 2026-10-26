from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass
class ParseStats:
    service: int = 0
    forwarded: int = 0
    empty: int = 0
    malformed: int = 0


@dataclass(frozen=True)
class ParsedMessage:
    message_id: int
    role: Literal["owner", "them"]
    text: str
    ts: datetime


@dataclass
class ParsedChat:
    chat_id: int
    name: str
    messages: list[ParsedMessage] = field(default_factory=list)
    raw_message_count: int = 0
    stats: ParseStats = field(default_factory=ParseStats)


@dataclass(frozen=True)
class ParsedExport:
    format: Literal["full", "single"]
    owner_id: int
    chats: list[ParsedChat]
