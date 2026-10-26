from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from tgtwin.ingestion.models import ParsedChat, ParsedExport, ParsedMessage, ParseStats

FORWARD_KEYS = ("forwarded_from", "forwarded_from_id", "saved_from")


class ExportFormatError(ValueError):
    pass


class OwnerIdError(ValueError):
    pass


def parse_export(path: str | Path, explicit_owner_id: int | None = None) -> ParsedExport:
    with Path(path).open(encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, dict):
        raise ExportFormatError("result.json: ожидался объект")

    owner_id = resolve_owner_id(data, explicit_owner_id)
    if owner_id is None:
        raise OwnerIdError("owner_id не найден: нет personal_information.user_id и --owner-id")

    raw_chats, export_format = _extract_chats(data)
    chats = [_parse_chat(raw, owner_id) for raw in raw_chats]
    return ParsedExport(format=export_format, owner_id=owner_id, chats=chats)


def resolve_owner_id(data: Mapping[str, Any], explicit_owner_id: int | None) -> int | None:
    personal = data.get("personal_information")
    if isinstance(personal, Mapping):
        raw_owner_id = personal.get("user_id")
        try:
            if raw_owner_id is not None:
                return int(raw_owner_id)
        except (TypeError, ValueError):
            pass
    return explicit_owner_id


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if not isinstance(value, list):
        return ""

    parts: list[str] = []
    for fragment in value:
        if isinstance(fragment, str):
            parts.append(fragment)
        elif isinstance(fragment, Mapping):
            text = fragment.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts).strip()


def _extract_chats(
    data: Mapping[str, Any],
) -> tuple[list[Mapping[str, Any]], Literal["full", "single"]]:
    for key in ("personal_chats", "chats"):
        container = data.get(key)
        raw_list: Any = None
        if isinstance(container, Mapping):
            raw_list = container.get("list")
        elif isinstance(container, list):
            raw_list = container
        if isinstance(raw_list, list):
            chats = [
                chat
                for chat in raw_list
                if isinstance(chat, Mapping) and chat.get("type") == "personal_chat"
            ]
            return chats, "full"

    messages = data.get("messages")
    if isinstance(messages, list):
        chat_type = data.get("type")
        if chat_type is not None and chat_type != "personal_chat":
            raise ExportFormatError(f"экспорт одного чата: неподдерживаемый type={chat_type!r}")
        return [data], "single"

    raise ExportFormatError("result.json: не найдены ни список чатов, ни корневой messages")


def _parse_chat(raw: Mapping[str, Any], owner_id: int) -> ParsedChat:
    chat_id = _as_int(raw.get("id"))
    if chat_id is None:
        raise ExportFormatError("у чата отсутствует целочисленный id")
    raw_name = raw.get("name")
    name = raw_name.strip() if isinstance(raw_name, str) and raw_name.strip() else f"chat {chat_id}"
    raw_messages = raw.get("messages")
    if not isinstance(raw_messages, list):
        raw_messages = []

    stats = ParseStats()
    messages: list[ParsedMessage] = []
    for raw_message in raw_messages:
        parsed = _parse_message(raw_message, owner_id, stats)
        if parsed is not None:
            messages.append(parsed)
    messages.sort(key=lambda message: (message.ts, message.message_id))

    return ParsedChat(
        chat_id=chat_id,
        name=name,
        messages=messages,
        raw_message_count=len(raw_messages),
        stats=stats,
    )


def _parse_message(
    raw: Any,
    owner_id: int,
    stats: ParseStats,
) -> ParsedMessage | None:
    if not isinstance(raw, Mapping):
        stats.malformed += 1
        return None
    if raw.get("type") != "message":
        stats.service += 1
        return None
    if any(raw.get(key) for key in FORWARD_KEYS):
        stats.forwarded += 1
        return None

    text = flatten_text(raw.get("text"))
    if not text:
        stats.empty += 1
        return None

    message_id = _as_int(raw.get("id"))
    if message_id is None:
        stats.malformed += 1
        return None

    ts = _parse_ts(raw.get("date_unixtime"))
    if ts is None:
        stats.malformed += 1
        return None

    from_id = raw.get("from_id")
    role: Literal["owner", "them"] = (
        "owner" if isinstance(from_id, str) and from_id == f"user{owner_id}" else "them"
    )
    return ParsedMessage(message_id=message_id, role=role, text=text, ts=ts)


def _parse_ts(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(value), tz=UTC)
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _as_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
