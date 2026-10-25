from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.core.models import Action, ChatMessage, Context, HistoryItem, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.llm import LLMStep, build_messages


def incoming() -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=99,
        text="последнее",
        from_owner=False,
        ts=datetime.now(UTC),
    )


def history(*roles: str) -> list[HistoryItem]:
    return [
        HistoryItem(message_id=i + 1, role=role, text=f"сообщение {i + 1}", ts=datetime.now(UTC))
        for i, role in enumerate(roles)
    ]


class CaptureProvider:
    def __init__(self, response: str = "ok") -> None:
        self.response = response
        self.calls: list[tuple[str, list[ChatMessage]]] = []

    async def generate(self, system: str, messages: list[ChatMessage]) -> str:
        self.calls.append((system, messages))
        return self.response


async def run_step(items: list[HistoryItem], response: str) -> tuple[Context, CaptureProvider]:
    provider = CaptureProvider(response)
    ctx = Context(msg=incoming(), history=items, system="sys")
    await Pipeline([LLMStep(provider)]).run(ctx)
    return ctx, provider


async def test_roles_mapped_and_merged() -> None:
    ctx, provider = await run_step(
        history("them", "owner", "owner", "them", "bot", "them"), "ok"
    )
    messages = provider.calls[0][1]
    assert [(m.role, m.content) for m in messages] == [
        ("user", "сообщение 1"),
        ("assistant", "сообщение 2\nсообщение 3"),
        ("user", "сообщение 4"),
        ("assistant", "сообщение 5"),
        ("user", "сообщение 6"),
    ]
    assert ctx.action == Action.REPLY
    assert ctx.reply == "ok"


async def test_leading_assistant_dropped() -> None:
    _, provider = await run_step(history("owner", "owner", "them"), "ok")
    messages = provider.calls[0][1]
    assert [m.role for m in messages] == ["user"]
    assert messages[0].content == "сообщение 3"


async def test_last_not_them_stops() -> None:
    ctx, provider = await run_step(history("them", "owner"), "ok")
    assert ctx.stop is True
    assert ctx.action == Action.NONE
    assert provider.calls == []


async def test_empty_history_uses_current_text() -> None:
    ctx, provider = await run_step([], "ok")
    assert provider.calls[0][1] == [ChatMessage(role="user", content="последнее")]
    assert ctx.action == Action.REPLY


async def test_system_passed_to_provider() -> None:
    _, provider = await run_step(history("them"), "ok")
    assert provider.calls[0][0] == "sys"


async def test_escalate_token() -> None:
    ctx, _ = await run_step(history("them"), "[ESCALATE]")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None


async def test_empty_reply_escalates() -> None:
    ctx, _ = await run_step(history("them"), "   ")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None


def test_build_messages_all_assistant() -> None:
    assert build_messages(history("owner", "bot"), "x") is None
