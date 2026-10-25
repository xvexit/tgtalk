from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.fakes import FakeMessageRepo
from tgtwin.core.models import Context, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.record import RecordStep


@pytest.mark.asyncio
async def test_record_echo_owner_stopped(caplog) -> None:
    repo = FakeMessageRepo()
    repo.seed(1, 5, role="bot", text="мой ответ")
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=5,
        text="hi",
        from_owner=True,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg)
    res = await Pipeline([RecordStep(repo)]).run(ctx)
    assert res.stop is True
    assert "echo_of_bot_reply" in caplog.text


@pytest.mark.asyncio
async def test_record_owner_duplicate_stopped_without_echo(caplog) -> None:
    repo = FakeMessageRepo()
    repo.seed(1, 6, role="owner", text="моё")
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=6,
        text="hi",
        from_owner=True,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg)
    res = await Pipeline([RecordStep(repo)]).run(ctx)
    assert res.stop is True
    assert "echo_of_bot_reply" not in caplog.text


@pytest.mark.asyncio
async def test_record_roles() -> None:
    repo = FakeMessageRepo()
    msg = IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=7,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )
    ctx = Context(msg=msg)
    await Pipeline([RecordStep(repo)]).run(ctx)
    assert repo.rows[(1, 7)].role == "them"
