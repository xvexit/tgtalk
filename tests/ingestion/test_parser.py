from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from tgtwin.ingestion.parser import OwnerIdError, flatten_text, parse_export


def _write(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _msg(
    message_id: int,
    from_id: str,
    text: Any,
    date_unixtime: str = "1700000000",
    **extra: Any,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": message_id,
        "type": "message",
        "date": "1999-01-01T00:00:00",
        "date_unixtime": date_unixtime,
        "from_id": from_id,
        "text": text,
    }
    payload.update(extra)
    return payload


def _full_export() -> dict[str, Any]:
    return {
        "personal_information": {"user_id": 111},
        "chats": {
            "list": [
                {
                    "id": 111,
                    "name": "Saved",
                    "type": "saved_messages",
                    "messages": [_msg(90, "user111", "не брать")],
                },
                {
                    "id": 222,
                    "name": "Алиса",
                    "type": "personal_chat",
                    "messages": [
                        _msg(1, "user111", "Привет"),
                        _msg(2, "user222", ["Ну ", {"type": "bold", "text": "да"}], "1700000100"),
                        {"id": 3, "type": "service", "date_unixtime": "1700000150", "text": ""},
                        _msg(4, "user222", "пересланное", "1700000200", forwarded_from="Кто-то"),
                        _msg(5, "user222", "", "1700000300"),
                        _msg(6, "user111", [{"type": "link", "text": "https://x"}], "1700000400"),
                    ],
                },
                {
                    "id": 333,
                    "name": "Группа",
                    "type": "private_group",
                    "messages": [_msg(91, "user222", "не брать")],
                },
            ]
        },
    }


def test_full_export_chats_list(tmp_path: Path) -> None:
    parsed = parse_export(_write(tmp_path, _full_export()))

    assert parsed.format == "full"
    assert parsed.owner_id == 111
    assert [c.chat_id for c in parsed.chats] == [222]
    chat = parsed.chats[0]
    assert chat.name == "Алиса"
    assert chat.raw_message_count == 6
    assert [(m.message_id, m.role, m.text) for m in chat.messages] == [
        (1, "owner", "Привет"),
        (2, "them", "Ну да"),
        (6, "owner", "https://x"),
    ]
    assert chat.messages[0].ts == datetime.fromtimestamp(1700000000, tz=UTC)
    assert chat.stats.service == 1
    assert chat.stats.forwarded == 1
    assert chat.stats.empty == 1
    assert chat.stats.malformed == 0


def test_full_export_personal_chats_key(tmp_path: Path) -> None:
    data = {
        "personal_chats": {
            "list": [
                {
                    "id": 222,
                    "name": "Алиса",
                    "type": "personal_chat",
                    "messages": [_msg(1, "user111", "привет")],
                }
            ]
        }
    }
    parsed = parse_export(_write(tmp_path, data), explicit_owner_id=111)

    assert parsed.format == "full"
    assert parsed.owner_id == 111
    assert parsed.chats[0].messages[0].role == "owner"


def test_single_chat_root_messages(tmp_path: Path) -> None:
    data = {
        "id": 444,
        "name": "Боб",
        "type": "personal_chat",
        "messages": [
            _msg(1, "user111", "моё"),
            _msg(2, "user444", "его"),
        ],
    }
    parsed = parse_export(_write(tmp_path, data), explicit_owner_id=111)

    assert parsed.format == "single"
    assert parsed.owner_id == 111
    assert parsed.chats[0].chat_id == 444
    assert [m.role for m in parsed.chats[0].messages] == ["owner", "them"]


def test_file_owner_id_wins_over_explicit(tmp_path: Path) -> None:
    parsed = parse_export(_write(tmp_path, _full_export()), explicit_owner_id=999)

    assert parsed.owner_id == 111
    assert parsed.chats[0].messages[0].role == "owner"


def test_missing_owner_id_raises(tmp_path: Path) -> None:
    data = {"messages": [_msg(1, "user111", "привет")]}

    with pytest.raises(OwnerIdError):
        parse_export(_write(tmp_path, data))


def test_single_group_is_rejected(tmp_path: Path) -> None:
    data = {
        "id": 555,
        "name": "Группа",
        "type": "private_group",
        "messages": [_msg(1, "user111", "привет")],
    }

    with pytest.raises(ValueError):
        parse_export(_write(tmp_path, data), explicit_owner_id=111)


def test_flatten_text_ignores_non_text_fragments() -> None:
    value = ["а", {"type": "bold", "text": "б"}, {"type": "emoji"}, 42]

    assert flatten_text(value) == "аб"
    assert flatten_text("  привет  ") == "привет"
    assert flatten_text(None) == ""
