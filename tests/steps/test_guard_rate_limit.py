from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.core.models import Action, Context, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.guard_rate_limit import GuardRateLimitStep


def incoming(from_owner: bool = False) -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=1,
        text="hi",
        from_owner=from_owner,
        ts=datetime.now(UTC),
    )


class FakeLogRepo:
    def __init__(self, sent_count: int) -> None:
        self.sent_count = sent_count
        self.queries: list[tuple[int, datetime]] = []

    async def count_sent_since(self, chat_id: int, since: datetime) -> int:
        self.queries.append((chat_id, since))
        return self.sent_count


async def test_under_limit_passes() -> None:
    repo = FakeLogRepo(sent_count=9)
    ctx = Context(msg=incoming())
    await Pipeline([GuardRateLimitStep(repo, max_per_hour=10)]).run(ctx)
    assert ctx.stop is False
    assert ctx.action == Action.NONE


async def test_limit_exceeded_stops(caplog) -> None:
    repo = FakeLogRepo(sent_count=10)
    ctx = Context(msg=incoming())
    await Pipeline([GuardRateLimitStep(repo, max_per_hour=10)]).run(ctx)
    assert ctx.stop is True
    assert ctx.action == Action.NONE
    assert "rate_limit_replies_exceeded" in caplog.text


async def test_owner_bypasses() -> None:
    repo = FakeLogRepo(sent_count=10)
    ctx = Context(msg=incoming(from_owner=True))
    await Pipeline([GuardRateLimitStep(repo, max_per_hour=10)]).run(ctx)
    assert ctx.stop is False
    assert repo.queries == []


async def test_disabled_when_zero() -> None:
    repo = FakeLogRepo(sent_count=10)
    ctx = Context(msg=incoming())
    await Pipeline([GuardRateLimitStep(repo, max_per_hour=0)]).run(ctx)
    assert ctx.stop is False
