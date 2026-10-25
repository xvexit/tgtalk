from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.core.models import Action, Context, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.steps.postprocess import PostprocessStep, delay_for


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
    assert len(ctx.reply) == 500


async def test_delay_formula() -> None:
    assert delay_for("x" * 10) == 2.0
    assert delay_for("x" * 100) == 6.5
    assert delay_for("x" * 500) == 8.0
    ctx = await run("x" * 100)
    assert ctx.meta["delay"] == 6.5


async def test_empty_after_strip_stops() -> None:
    ctx = await run('  ""  ')
    assert ctx.stop is True
    assert ctx.reply is None


async def test_link_escalates() -> None:
    ctx = await run("зайди на https://example.com")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None


async def test_mention_escalates() -> None:
    ctx = await run("спроси @ivan")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None


async def test_tme_link_escalates() -> None:
    ctx = await run("вот t.me/durov")
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None


async def test_already_escalate_untouched() -> None:
    ctx = Context(msg=incoming(), reply=None, action=Action.ESCALATE)
    await Pipeline([PostprocessStep()]).run(ctx)
    assert ctx.action == Action.ESCALATE
    assert ctx.reply is None
