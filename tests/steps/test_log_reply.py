from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.core.models import Context, IncomingMessage, ReplyLogEntry, ResolvedConfig
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.log_reply import LogReplyStep


def incoming() -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=42,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )


class FakeLogRepo:
    def __init__(self) -> None:
        self.entries: list[ReplyLogEntry] = []
        self.next_id = 1

    async def add(self, entry: ReplyLogEntry) -> int:
        self.entries.append(entry)
        log_id = self.next_id
        self.next_id += 1
        return log_id


async def test_entry_fields() -> None:
    repo = FakeLogRepo()
    ctx = Context(
        msg=incoming(),
        cfg=ResolvedConfig(),
        reply="ответ",
        meta={"history_ids": [1, 2], "system_hash": "abc"},
    )
    await Pipeline([LogReplyStep(repo, "test-model")]).run(ctx)
    entry = repo.entries[0]
    assert entry.chat_id == 1
    assert entry.trigger_message_id == 42
    assert entry.mode == "dry_run"
    assert entry.reply == "ответ"
    assert entry.sent is False
    assert entry.context == {"history_ids": [1, 2], "system_hash": "abc", "model": "test-model"}
    assert ctx.meta["reply_log_id"] == 1


async def test_context_has_no_texts() -> None:
    repo = FakeLogRepo()
    ctx = Context(msg=incoming(), cfg=ResolvedConfig(), reply=None)
    await Pipeline([LogReplyStep(repo, "m")]).run(ctx)
    entry = repo.entries[0]
    assert "text" not in entry.context
    assert entry.reply is None


async def test_none_reply_logged_too() -> None:
    repo = FakeLogRepo()
    ctx = Context(msg=incoming(), cfg=ResolvedConfig(), reply=None)
    await Pipeline([LogReplyStep(repo, "m")]).run(ctx)
    assert len(repo.entries) == 1
