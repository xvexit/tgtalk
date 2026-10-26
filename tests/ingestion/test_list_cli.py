from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tgtwin.ingestion.__main__ import main


def _msg(message_id: int, from_id: str, text: str, ts: datetime) -> dict[str, Any]:
    return {
        "id": message_id,
        "type": "message",
        "date_unixtime": str(int(ts.timestamp())),
        "from_id": from_id,
        "text": text,
    }


def _chat(
    chat_id: int,
    name: str,
    owner_ids: list[int],
    them_ids: list[int],
    start: datetime,
) -> dict[str, Any]:
    messages = [
        _msg(index + 1, "user111", f"owner-{index}", start)
        for index in range(owner_ids)
    ]
    messages.extend(
        _msg(100 + index, f"user{chat_id}", f"them-{index}", start)
        for index in range(them_ids)
    )
    return {
        "id": chat_id,
        "name": name,
        "type": "personal_chat",
        "messages": messages,
    }


def _write(tmp_path: Path) -> Path:
    data = {
        "personal_information": {"user_id": 111},
        "chats": {
            "list": [
                _chat(1, "One", 3, 1, datetime(2026, 1, 1, tzinfo=UTC)),
                _chat(2, "Two", 1, 5, datetime(2026, 2, 1, tzinfo=UTC)),
                _chat(3, "Three", 0, 2, datetime(2026, 3, 1, tzinfo=UTC)),
            ]
        },
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_list_default_sort_and_no_names(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path)

    assert main(["list", str(path), "--limit", "2"]) == 0
    output = capsys.readouterr().out

    assert "One" not in output
    assert "Two" not in output
    assert "chats: 2 shown / 3 total" in output
    assert output.index("          1") < output.index("          2")


def test_list_sort_total(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path)

    assert main(["list", str(path), "--sort", "total", "--limit", "2"]) == 0
    output = capsys.readouterr().out

    assert output.index("          2") < output.index("          1")


def test_list_sort_last(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path)

    assert main(["list", str(path), "--sort", "last", "--limit", "1"]) == 0
    output = capsys.readouterr().out

    assert "          3" in output
    assert "2026-03-01 00:00:00" in output
    assert "2026-02-01 00:00:00" not in output


def test_list_min_mine(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path)

    assert main(["list", str(path), "--min-mine", "2"]) == 0
    output = capsys.readouterr().out

    assert "          1" in output
    assert "          2" not in output
    assert "          3" not in output


def test_list_names_flag(tmp_path: Path, capsys) -> None:
    path = _write(tmp_path)

    assert main(["list", str(path), "--names", "--limit", "1"]) == 0
    output = capsys.readouterr().out

    assert "One" in output
