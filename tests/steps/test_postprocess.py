from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tgtwin.core.models import Action, Context, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.postprocess import PostprocessStep, delay_for, split_replies


def incoming() -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        connection_id="c1",
        chat_id=1,
        message_id=1,
        text="hi",
        from_owner=False,
        ts=datetime.now(UTC),
    )


async def run(text: str) -> Context:
    ctx = Context(msg=incoming(), reply=text, action=Action.REPLY)
    await Pipeline([PostprocessStep()]).run(ctx)
    return ctx


async def test_strip_whitespace() -> None:
    ctx = await run("   привет   ")
    assert ctx.reply == "привет"


async def test_strip_quotes() -> None:
    ctx = await run('  "привет"  ')
    assert ctx.reply == "привет"
    ctx = await run("«да»")
    assert ctx.reply == "да"
    ctx = await run("''x''")
    assert ctx.reply == "x"


async def test_max_chars_truncate() -> None:
    ctx = await run("а" * 600)
    assert len(ctx.reply) == 200


async def test_delay_formula() -> None:
    assert delay_for("x" * 10) == pytest.approx(1.4)
    assert delay_for("x" * 100) == pytest.approx(5.0)
    assert delay_for("x" * 500) == pytest.approx(5.0)
    ctx = await run("x" * 100)
    assert ctx.meta["delay"] == pytest.approx(5.0)


def test_split_replies_keeps_three_and_drops_empty() -> None:
    assert split_replies("  раз\n\nдва  \n три \nчетыре") == ["раз", "два", "три"]


def test_split_replies_truncates_each_to_200() -> None:
    replies = split_replies("а" * 250 + "\n" + "б" * 250)
    assert [len(reply) for reply in replies] == [200, 200]


async def test_multiline_reply_keeps_series() -> None:
    ctx = await run("раз\nдва\nтри\nчетыре")
    assert ctx.reply == "раз\nдва\nтри"
    assert ctx.meta["replies"] == ["раз", "два", "три"]
    assert len(ctx.meta["delays"]) == 3


async def test_empty_after_strip_stops() -> None:
    ctx = await run('  ""  ')
    assert ctx.stop is True
    assert ctx.reply is None


async def test_link_escalates(caplog) -> None:
    ctx = await run("зайди на https://example.com")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None
    reasons = [getattr(r, "escalate_reason", None) for r in caplog.records]
    assert "link_or_mention" in reasons


async def test_mention_escalates() -> None:
    ctx = await run("спроси @ivan")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None


async def test_tme_link_escalates() -> None:
    ctx = await run("вот t.me/durov")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None


async def test_link_in_any_line_escalates() -> None:
    ctx = await run("привет\nзайди на https://example.com\nкак дела")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None


async def test_quotes_stripped_per_line() -> None:
    ctx = await run('"привет"\n"как дела"')
    assert ctx.meta["replies"] == ["привет", "как дела"]


async def test_already_escalate_untouched() -> None:
    ctx = Context(msg=incoming(), reply=None, action=Action.ESCALATE)
    await Pipeline([PostprocessStep()]).run(ctx)
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None
