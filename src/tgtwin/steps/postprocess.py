from __future__ import annotations

import re

from tgtwin.core.models import Action, Context

QUOTE_PAIRS: dict[str, str] = {
    '"': '"',
    "'": "'",
    "`": "`",
    "«": "»",
    "“": "”",
    "„": "“",
}
LINK_OR_MENTION_RE = re.compile(r"https?://\S+|t\.me/\S+|@[A-Za-z0-9_]{2,}")


def strip_quotes(text: str) -> str:
    result = text.strip()
    while len(result) >= 2 and result[0] in QUOTE_PAIRS and result[-1] == QUOTE_PAIRS[result[0]]:
        result = result[1:-1].strip()
    return result


def delay_for(text: str) -> float:
    return min(1.5 + 0.05 * len(text), 8.0)


class PostprocessStep:
    def __init__(self, max_chars: int = 500) -> None:
        self.max_chars = max_chars

    async def handle(self, ctx: Context) -> None:
        if ctx.action == Action.ESCALATE or ctx.reply is None:
            return
        text = strip_quotes(ctx.reply)
        if not text:
            ctx.reply = None
            ctx.stop = True
            return
        if LINK_OR_MENTION_RE.search(text):
            ctx.reply = None
            ctx.action = Action.ESCALATE
            return
        text = text[: self.max_chars]
        ctx.reply = text
        ctx.meta["delay"] = delay_for(text)
