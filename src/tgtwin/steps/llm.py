from __future__ import annotations

import logging

from tgtwin.core.models import Action, ChatMessage, Context, HistoryItem
from tgtwin.core.protocols import LLMProvider

logger = logging.getLogger(__name__)

ESCALATE_TOKEN = "[ESCALATE]"


def build_messages(history: list[HistoryItem], current_text: str) -> list[ChatMessage] | None:
    if not history:
        return [ChatMessage(role="user", content=current_text)]
    merged: list[ChatMessage] = []
    for item in history:
        role = "user" if item.role == "them" else "assistant"
        if not item.text.strip():
            continue
        if merged and merged[-1].role == role:
            merged[-1] = ChatMessage(role=role, content=f"{merged[-1].content}\n{item.text}")
        else:
            merged.append(ChatMessage(role=role, content=item.text))
    while merged and merged[0].role != "user":
        merged.pop(0)
    if not merged or merged[-1].role != "user":
        return None
    return merged


class LLMStep:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def handle(self, ctx: Context) -> None:
        if ctx.stop or ctx.reply is not None:
            return
        messages = build_messages(ctx.history, ctx.msg.text or "")
        if messages is None:
            ctx.stop = True
            return
        reply = await self.provider.generate(ctx.system, messages)
        text = (reply or "").strip()
        if not text:
            logger.warning(
                "llm_empty_reply",
                extra={"chat_id": ctx.msg.chat_id, "message_id": ctx.msg.message_id},
            )
            ctx.action = Action.ESCALATE
            ctx.reply = None
            return
        if ESCALATE_TOKEN in text:
            logger.info(
                "llm_escalate",
                extra={"chat_id": ctx.msg.chat_id, "message_id": ctx.msg.message_id},
            )
            ctx.action = Action.ESCALATE
            ctx.reply = None
            return
        ctx.reply = text
        ctx.action = Action.REPLY
