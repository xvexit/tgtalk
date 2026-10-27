from __future__ import annotations

import logging
import re

from tgtwin.core.models import Action, Context

logger = logging.getLogger(__name__)

QUOTE_PAIRS: dict[str, str] = {
    '"': '"',
    "'": "'",
    "`": "`",
    "«": "»",
    "“": "”",
    "„": "“",
}
LINK_OR_MENTION_RE = re.compile(r"https?://\S+|t\.me/\S+|@[A-Za-z0-9_]{2,}")
MAX_REPLIES = 3
MAX_REPLY_CHARS = 200


def strip_quotes(text: str) -> str:
    result = text.strip()
    while len(result) >= 2 and result[0] in QUOTE_PAIRS and result[-1] == QUOTE_PAIRS[result[0]]:
        result = result[1:-1].strip()
    return result


def delay_for(text: str) -> float:
    return min(1.0 + 0.04 * len(text), 5.0)


def split_replies(text: str, max_replies: int = MAX_REPLIES) -> list[str]:
    replies: list[str] = []
    for raw_line in text.splitlines():
        line = strip_quotes(raw_line.strip())
        if line and line[0] in QUOTE_PAIRS:
            line = line[1:].strip()
        if line and line[-1] in QUOTE_PAIRS.values():
            line = line[:-1].strip()
        if not line:
            continue
        replies.append(line[:MAX_REPLY_CHARS])
        if len(replies) >= max_replies:
            break
    return replies


class PostprocessStep:
    def __init__(self, max_replies: int = MAX_REPLIES, max_chars: int = MAX_REPLY_CHARS) -> None:
        self.max_replies = max_replies
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
            logger.warning(
                "escalate",
                extra={
                    "chat_id": ctx.msg.chat_id,
                    "message_id": ctx.msg.message_id,
                    "escalate_reason": "link_or_mention",
                },
            )
            ctx.reply = None
            ctx.action = Action.ESCALATE
            return
        replies = split_replies(text, self.max_replies)
        if not replies:
            ctx.reply = None
            ctx.stop = True
            return
        replies = [reply[: self.max_chars] for reply in replies]
        ctx.reply = "\n".join(replies)
        ctx.meta["replies"] = replies
        ctx.meta["delays"] = [delay_for(reply) for reply in replies]
        ctx.meta["delay"] = ctx.meta["delays"][0]
