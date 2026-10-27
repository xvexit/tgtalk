from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

from tests.fakes import DummyBot, DummyChat, DummyMsg, FakeMessageRepo, FakeReplyLogRepo, FakeSender
from tgtwin.adapters.telegram.handlers import business_message
from tgtwin.adapters.telegram.owner_resolver import OwnerResolver
from tgtwin.adapters.telegram.sender import TelegramBusinessSender
from tgtwin.core.models import Action, Context, Mode, ResolvedConfig
from tgtwin.core.pipeline import Pipeline
from tgtwin.core.protocols import Step
from tgtwin.steps.guard_owner import GuardOwnerStep
from tgtwin.steps.guard_rate_limit import GuardRateLimitStep
from tgtwin.steps.guard_takeover import GuardTakeoverStep
from tgtwin.steps.record import RecordStep
from tgtwin.steps.resolve_config import ResolveConfigStep

OWNER_ID = 777


class ReplyStep(Step):
    def __init__(self, reply: str | None = "ок", action: Action = Action.REPLY) -> None:
        self.reply = reply
        self.action = action

    async def handle(self, ctx: Context) -> None:
        ctx.reply = self.reply
        ctx.action = self.action
        ctx.meta["delay"] = 0.0
        ctx.meta["reply_log_id"] = 7


class RaisingSender(FakeSender):
    async def send(self, msg, text: str, delay: float) -> int | None:
        raise RuntimeError("telegram error")


class SeriesStep(Step):
    async def handle(self, ctx: Context) -> None:
        ctx.reply = "раз\nдва\nтри"
        ctx.meta["replies"] = ["раз", "два", "три"]
        ctx.meta["delays"] = [1.0, 2.0, 3.0]
        ctx.meta["reply_log_id"] = 7
        ctx.action = Action.REPLY


def make_router(sender, repo, log_repo, steps):
    bot = DummyBot()
    resolver = OwnerResolver(bot)
    resolver.set("bc1", owner_id=OWNER_ID, user_chat_id=OWNER_ID)
    pipeline = Pipeline(steps)
    router = business_message.setup(bot, pipeline, resolver, sender, log_repo)
    observers = router.observers["business_message"].handlers
    assert observers
    handler = observers[-1].callback
    return handler


def them_msg(message_id: int, full_name: str | None = "Иван") -> DummyMsg:
    return DummyMsg(
        message_id=message_id,
        chat=DummyChat(chat_id=1, full_name=full_name),
        text="привет",
        from_user_id=555,
        date=datetime.now(UTC),
    )


def owner_msg(message_id: int) -> DummyMsg:
    return DummyMsg(
        message_id=message_id,
        chat=DummyChat(chat_id=1, full_name="Владелец"),
        text="я сам",
        from_user_id=OWNER_ID,
        date=datetime.now(UTC),
    )


async def test_echo_of_bot_not_recorded_and_no_send(caplog) -> None:
    repo = FakeMessageRepo()
    repo.seed(1, 5, role="bot", text="мой ответ")
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()
    handler = make_router(
        sender,
        repo,
        log_repo,
        [ResolveConfigStep(), RecordStep(repo), GuardOwnerStep(), ReplyStep()],
    )
    echo = owner_msg(5)
    await handler(echo)
    assert sender.sent == []
    assert sender.notified == []
    assert await repo.role_of(1, 5) == "bot"
    assert "echo_of_bot_reply" in caplog.text


async def test_escalate_notifies_owner_with_name() -> None:
    repo = FakeMessageRepo()
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()
    handler = make_router(
        sender,
        repo,
        log_repo,
        [ResolveConfigStep(), RecordStep(repo), ReplyStep(reply=None, action=Action.ESCALATE)],
    )
    await handler(them_msg(10, full_name="Мария"))
    assert sender.notified == [("bc1", "тут нужен ты: Мария")]
    assert sender.sent == []


async def test_escalate_fallback_name() -> None:
    repo = FakeMessageRepo()
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()
    handler = make_router(
        sender,
        repo,
        log_repo,
        [ResolveConfigStep(), RecordStep(repo), ReplyStep(reply=None, action=Action.ESCALATE)],
    )
    await handler(them_msg(10, full_name=None))
    assert sender.notified == [("bc1", "тут нужен ты: собеседник")]


async def test_send_failure_logged_and_no_mark_sent(caplog) -> None:
    repo = FakeMessageRepo()
    sender = RaisingSender()
    log_repo = FakeReplyLogRepo()
    handler = make_router(
        sender, repo, log_repo, [ResolveConfigStep(), RecordStep(repo), ReplyStep()]
    )
    await handler(them_msg(10))
    assert "send_failed" in caplog.text
    assert log_repo.marked == []
    await handler(them_msg(11))


async def test_successful_send_marks_sent() -> None:
    repo = FakeMessageRepo()
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()
    handler = make_router(
        sender, repo, log_repo, [ResolveConfigStep(), RecordStep(repo), ReplyStep()]
    )
    await handler(them_msg(10))
    assert len(sender.sent) == 1
    assert log_repo.marked == [(7, True)]


async def test_dry_run_sender_none_no_mark_sent() -> None:
    repo = FakeMessageRepo()
    log_repo = FakeReplyLogRepo()

    class NoneSender(FakeSender):
        async def send(self, msg, text: str, delay: float) -> int | None:
            self.sent.append((msg, text, delay))
            return None

    handler = make_router(
        sender=NoneSender(),
        repo=repo,
        log_repo=log_repo,
        steps=[ResolveConfigStep(), RecordStep(repo), ReplyStep()],
    )
    await handler(them_msg(10))
    assert log_repo.marked == []


async def test_mode_off_skips_send() -> None:
    repo = FakeMessageRepo()
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()

    class OffReplyStep(ReplyStep):
        async def handle(self, ctx: Context) -> None:
            await super().handle(ctx)
            ctx.cfg = ResolvedConfig(mode=Mode.OFF)

    handler = make_router(
        sender,
        repo,
        log_repo,
        [ResolveConfigStep(), RecordStep(repo), OffReplyStep()],
    )
    await handler(them_msg(10))
    assert sender.sent == []
    assert log_repo.marked == []


async def test_takeover_prevents_second_reply() -> None:
    repo = FakeMessageRepo()
    repo.last_owner = datetime.now(UTC)
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()
    handler = make_router(
        sender,
        repo,
        log_repo,
        [ResolveConfigStep(), RecordStep(repo), GuardTakeoverStep(repo, default_hours=3), ReplyStep()],
    )
    await handler(them_msg(10))
    assert sender.sent == []
    assert sender.notified == []


async def test_rate_limit_notifies_owner_once_per_hour(monkeypatch) -> None:
    repo = FakeMessageRepo()
    sender = FakeSender()
    log_repo = FakeReplyLogRepo(sent_count=10)
    clock = {"t": 10000.0}
    monkeypatch.setattr(business_message, "_clock", lambda: clock["t"])
    handler = make_router(
        sender,
        repo,
        log_repo,
        [ResolveConfigStep(), RecordStep(repo), GuardRateLimitStep(log_repo, max_per_hour=10)],
    )
    await handler(them_msg(10, full_name="Иван"))
    assert sender.notified == [("bc1", "лимит ответов исчерпан: Иван")]
    assert sender.sent == []
    await handler(them_msg(11, full_name="Иван"))
    assert len(sender.notified) == 1
    clock["t"] += 3600
    await handler(them_msg(12, full_name="Иван"))
    assert len(sender.notified) == 2
    assert sender.sent == []


async def test_lock_acquired_around_pipeline(monkeypatch) -> None:
    repo = FakeMessageRepo()
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()
    entered: list[object] = []

    class CountingLock(asyncio.Lock):
        async def __aenter__(self):
            entered.append(self)
            return await super().__aenter__()

    monkeypatch.setattr(business_message, "asyncio", SimpleNamespace(Lock=CountingLock))
    handler = make_router(
        sender, repo, log_repo, [ResolveConfigStep(), RecordStep(repo), ReplyStep()]
    )
    await handler(them_msg(10))
    await handler(them_msg(11))
    assert len(entered) == 2
    assert entered[0] is entered[1]


async def test_series_sends_each_part_and_marks_sent_once() -> None:
    repo = FakeMessageRepo()
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()
    handler = make_router(
        sender, repo, log_repo, [ResolveConfigStep(), RecordStep(repo), SeriesStep()]
    )

    await handler(them_msg(10))

    assert [text for _, text, _ in sender.sent] == ["раз", "два", "три"]
    assert [delay for _, _, delay in sender.sent] == [1.0, 2.0, 3.0]
    assert log_repo.marked == [(7, True)]


async def test_series_mid_error_stops_remaining(caplog) -> None:
    class FailSecondSender(FakeSender):
        def __init__(self) -> None:
            super().__init__()
            self.attempts = 0

        async def send(self, msg, text: str, delay: float) -> int | None:
            self.attempts += 1
            if self.attempts == 2:
                raise RuntimeError("telegram error")
            self.sent.append((msg, text, delay))
            return 12345

    repo = FakeMessageRepo()
    sender = FailSecondSender()
    log_repo = FakeReplyLogRepo()
    handler = make_router(
        sender, repo, log_repo, [ResolveConfigStep(), RecordStep(repo), SeriesStep()]
    )

    await handler(them_msg(10))

    assert [text for _, text, _ in sender.sent] == ["раз"]
    assert sender.attempts == 2
    assert log_repo.marked == [(7, True)]
    assert "send_failed" in caplog.text


async def test_series_keeps_lock_for_all_parts(monkeypatch) -> None:
    repo = FakeMessageRepo()
    log_repo = FakeReplyLogRepo()
    active = {"count": 0}
    seen: list[int] = []

    class TrackingLock(asyncio.Lock):
        async def __aenter__(self):
            active["count"] += 1
            return await super().__aenter__()

        async def __aexit__(self, *args):
            active["count"] -= 1
            return await super().__aexit__(*args)

    class LockAwareSender(FakeSender):
        async def send(self, msg, text: str, delay: float) -> int | None:
            seen.append(active["count"])
            return await super().send(msg, text, delay)

    monkeypatch.setattr(business_message, "asyncio", SimpleNamespace(Lock=TrackingLock))
    handler = make_router(
        LockAwareSender(), repo, log_repo, [ResolveConfigStep(), RecordStep(repo), SeriesStep()]
    )

    await handler(them_msg(10))

    assert seen == [1, 1, 1]
    assert active["count"] == 0


async def test_echo_of_each_series_part_is_not_answered() -> None:
    repo = FakeMessageRepo()
    sender = FakeSender()
    log_repo = FakeReplyLogRepo()
    bot = DummyBot(next_message_id=200)
    resolver = OwnerResolver(bot)
    resolver.set("bc1", owner_id=OWNER_ID, user_chat_id=OWNER_ID)
    business_sender = TelegramBusinessSender(bot, repo, resolver)
    handler = make_router(
        business_sender,
        repo,
        log_repo,
        [ResolveConfigStep(), RecordStep(repo), SeriesStep()],
    )

    await handler(them_msg(10))

    assert bot.send_message_calls == 3
    assert await repo.role_of(1, 200) == "bot"
    assert await repo.role_of(1, 201) == "bot"
    assert await repo.role_of(1, 202) == "bot"

    for message_id in (200, 201, 202):
        await handler(owner_msg(message_id))

    assert bot.send_message_calls == 3
    assert sender.sent == []
