from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict


class Action(StrEnum):
    NONE = "NONE"
    REPLY = "REPLY"
    ESCALATE = "ESCALATE"
    DRAFT = "DRAFT"


class Mode(StrEnum):
    OFF = "off"
    DRY_RUN = "dry_run"
    DRAFT = "draft"
    AUTO = "auto"


class ChatMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["user", "assistant"]
    content: str


class IncomingMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    channel: str
    connection_id: str
    chat_id: int
    message_id: int
    text: str | None
    from_owner: bool
    ts: AwareDatetime


class HistoryItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    role: Literal["them", "owner", "bot"]
    text: str
    ts: AwareDatetime


class Example(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str
    meta: dict[str, Any] = {}


class ResolvedConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    mode: Mode = Mode.DRY_RUN
    persona_id: int | None = None
    overrides: dict[str, Any] = {}


class StoredMessage(BaseModel):
    model_config = ConfigDict(frozen=True)

    chat_id: int
    message_id: int
    role: Literal["them", "owner", "bot"]
    text: str | None
    ts: AwareDatetime
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
