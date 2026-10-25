from __future__ import annotations

import hashlib
from datetime import UTC, datetime

import pytest

from tgtwin.core.models import Context, HistoryItem, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.build_context import BuildContextStep, load_persona


def incoming(chat_id: int = 1) -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=chat_id,
        message_id=1,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )


class Repo:
    def __init__(self, items: list[HistoryItem]) -> None:
        self.items = items
        self.requested_n: int | None = None

    async def last(self, chat_id: int, n: int) -> list[HistoryItem]:
        self.requested_n = n
        return self.items


async def test_persona_loaded_and_hash(tmp_path) -> None:
    persona_file = tmp_path / "persona.md"
    persona_file.write_text("секция стиля\n")
    persona = load_persona(str(persona_file))
    repo = Repo([])
    ctx = Context(msg=incoming())
    await Pipeline([BuildContextStep(repo, persona, history_limit=7)]).run(ctx)
    assert ctx.system == "секция стиля\n"
    assert ctx.meta["system_hash"] == hashlib.sha256(persona.encode("utf-8")).hexdigest()


async def test_history_limit_passed() -> None:
    repo = Repo([])
    ctx = Context(msg=incoming())
    await Pipeline([BuildContextStep(repo, "p", history_limit=15)]).run(ctx)
    assert repo.requested_n == 15


async def test_history_and_ids_stored() -> None:
    items = [
        HistoryItem(message_id=10, role="them", text="а", ts=datetime.now(UTC)),
        HistoryItem(message_id=11, role="owner", text="б", ts=datetime.now(UTC)),
    ]
    repo = Repo(items)
    ctx = Context(msg=incoming())
    await Pipeline([BuildContextStep(repo, "p", history_limit=30)]).run(ctx)
    assert ctx.history == items
    assert ctx.meta["history_ids"] == [10, 11]


def test_load_persona_missing_raises(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        load_persona(str(tmp_path / "нет.md"))
