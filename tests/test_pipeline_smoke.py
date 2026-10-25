from __future__ import annotations

from datetime import UTC, datetime

from tests.fakes import FakeMessageRepo, FakeReplyLogRepo
from tgtwin.app import build_pipeline
from tgtwin.config import Settings
from tgtwin.core.models import Action, Context, IncomingMessage
from tgtwin.llm.fake import FakeLLMProvider


async def test_pipeline_smoke() -> None:
    llm = FakeLLMProvider(response="ok")
    repo = FakeMessageRepo()
    log_repo = FakeReplyLogRepo()
    pipeline = build_pipeline(repo, llm, Settings(), log_repo, persona_text="персона")
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=10,
        text="привет",
        from_owner=False,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg)
    result = await pipeline.run(ctx)
    assert result.reply == "ok"
    assert result.action == Action.REPLY
    assert len(log_repo.entries) == 1
    assert log_repo.entries[0][1].sent is False
    assert log_repo.entries[0][1].context["model"] == "deepseek-flash"
