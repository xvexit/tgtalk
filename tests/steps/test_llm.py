from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.core.models import Action, ChatMessage, Context, HistoryItem, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.llm import LAST_MESSAGE_RULE, LLMStep, build_messages

TRIGGER_ID = 99
TRIGGER_TEXT = "последнее"


def incoming() -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=TRIGGER_ID,
        text=TRIGGER_TEXT,
        from_owner=False,
        ts=datetime.now(UTC),
    )


def items(*roles: str) -> list[HistoryItem]:
    return [
        HistoryItem(message_id=i + 1, role=role, text=f"сообщение {i + 1}", ts=datetime.now(UTC))
        for i, role in enumerate(roles)
    ]


def with_trigger(*roles: str) -> list[HistoryItem]:
    history = items(*roles)
    history[-1] = HistoryItem(
        message_id=TRIGGER_ID, role=history[-1].role, text=history[-1].text, ts=history[-1].ts
    )
    return history


class CaptureProvider:
    def __init__(self, response: str | None = "ok", finish_reason: str | None = "stop") -> None:
        self.response = response
        self.last_finish_reason = finish_reason
        self.calls: list[tuple[str, list[ChatMessage]]] = []

    async def generate(self, system: str, messages: list[ChatMessage]) -> str | None:
        self.calls.append((system, messages))
        return self.response


async def run_step(history: list[HistoryItem], response: str | None) -> tuple[Context, CaptureProvider]:
    provider = CaptureProvider(response)
    ctx = Context(msg=incoming(), history=history, system="sys")
    await Pipeline([LLMStep(provider)]).run(ctx)
    return ctx, provider


async def test_roles_mapped_and_merged() -> None:
    ctx, provider = await run_step(with_trigger("them", "owner", "owner", "them", "bot", "them"), "ok")
    messages = provider.calls[0][1]
    assert [(m.role, m.content) for m in messages] == [
        ("user", "сообщение 1"),
        ("assistant", "сообщение 2\nсообщение 3"),
        ("user", "сообщение 4"),
        ("assistant", "сообщение 5"),
        ("user", TRIGGER_TEXT),
    ]
    assert ctx.action == Action.REPLY
    assert ctx.reply == "ok"


async def test_last_message_not_merged_with_previous() -> None:
    ctx, provider = await run_step(with_trigger("them", "them", "them"), "ok")
    messages = provider.calls[0][1]
    assert [(m.role, m.content) for m in messages] == [
        ("user", "сообщение 1\nсообщение 2"),
        ("user", TRIGGER_TEXT),
    ]
    assert ctx.action == Action.REPLY


async def test_leading_assistant_dropped() -> None:
    _, provider = await run_step(with_trigger("owner", "owner", "them"), "ok")
    messages = provider.calls[0][1]
    assert [m.role for m in messages] == ["user"]
    assert messages[0].content == TRIGGER_TEXT


async def test_last_not_them_stops() -> None:
    ctx, provider = await run_step(items("them", "owner"), "ok")
    assert ctx.stop is True
    assert ctx.action == Action.NONE
    assert provider.calls == []


async def test_empty_history_uses_current_text() -> None:
    ctx, provider = await run_step([], "ok")
    assert provider.calls[0][1] == [ChatMessage(role="user", content=TRIGGER_TEXT)]
    assert ctx.action == Action.REPLY


async def test_system_has_last_message_rule() -> None:
    _, provider = await run_step(with_trigger("them"), "ok")
    system = provider.calls[0][0]
    assert LAST_MESSAGE_RULE in system
    assert system.startswith("sys")


def reasons(caplog) -> list[str]:
    return [getattr(r, "escalate_reason", None) for r in caplog.records if getattr(r, "escalate_reason", None)]


def finish_reasons(caplog) -> list[str]:
    return [getattr(r, "finish_reason", None) for r in caplog.records if getattr(r, "finish_reason", None)]


async def test_escalate_token_logs_reason(caplog) -> None:
    caplog.set_level("INFO")
    ctx, _ = await run_step(with_trigger("them"), "[ESCALATE]")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None
    assert reasons(caplog) == ["model_token"]


async def test_empty_reply_escalates_with_reason(caplog) -> None:
    ctx, _ = await run_step(with_trigger("them"), "   ")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None
    assert reasons(caplog) == ["empty_length"]
    assert finish_reasons(caplog) == ["stop"]


async def test_none_reply_escalates_with_reason(caplog) -> None:
    ctx, _ = await run_step(with_trigger("them"), None)
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None
    assert reasons(caplog) == ["empty_other"]
    assert finish_reasons(caplog) == ["stop"]


async def test_finish_reason_value_logged(caplog) -> None:
    provider = CaptureProvider(None, finish_reason="length")
    ctx = Context(msg=incoming(), history=with_trigger("them"), system="sys")
    await Pipeline([LLMStep(provider)]).run(ctx)
    assert ctx.action == Action.ESCALATE
    assert finish_reasons(caplog) == ["length"]


def test_build_messages_all_assistant() -> None:
    assert build_messages(items("owner", "bot"), TRIGGER_ID, "x") is None


def test_build_messages_unrecorded_trigger_kept_separate() -> None:
    messages = build_messages(items("them", "them"), TRIGGER_ID, "x")
    assert messages is not None
    assert messages[-1] == ChatMessage(role="user", content="x")
    assert messages[0] == ChatMessage(role="user", content="сообщение 1\nсообщение 2")
