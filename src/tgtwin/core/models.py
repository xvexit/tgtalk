from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class Action(str, Enum):
    NONE = "NONE"
    REPLY = "REPLY"
    ESCALATE = "ESCALATE"
    DRAFT = "DRAFT"


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    content: str


class IncomingMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel: str
    connection_id: str
    chat_id: int
    message_id: int
    text: str | None
    from_owner: bool
    ts: datetime


class HistoryItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: str
    text: str
    ts: datetime


class Example(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    meta: dict[str, Any] = {}


class ResolvedConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: str = "dry_run"
    persona_id: int | None = None
    overrides: dict[str, Any] = {}


class StoredMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    chat_id: int
    message_id: int
    role: str
    text: str | None
    ts: datetime
    connection_id: str | None = None


class Context(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    msg: IncomingMessage
    cfg: ResolvedConfig | None = None
    history: list[HistoryItem] = []
    examples: list[Example] = []
    system: str = ""
    reply: str | None = None
    action: Action = Action.NONE
    stop: bool = False
    meta: dict[str, Any] = {}
