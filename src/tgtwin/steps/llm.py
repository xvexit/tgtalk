from __future__ import annotations

import logging

from tgtwin.core.models import Action, ChatMessage, Context, HistoryItem
from tgtwin.core.protocols import LLMProvider

logger = logging.getLogger(__name__)

ESCALATE_TOKEN = "[ESCALATE]"
LAST_MESSAGE_RULE = (
    "Отвечай на ПОСЛЕДНЕЕ сообщение собеседника. "
    "Решение об [ESCALATE] принимай только по нему. "
    "Более ранние сообщения уже обработаны, считай их фоном"
)


def _merge_background(items: list[HistoryItem]) -> list[ChatMessage]:
    merged: list[ChatMessage] = []
    for item in items:
        role = "user" if item.role == "them" else "assistant"
        if not item.text.strip():
            continue
        if merged and merged[-1].role == role:
            merged[-1] = ChatMessage(role=role, content=f"{merged[-1].content}\n{item.text}")
        else:
            merged.append(ChatMessage(role=role, content=item.text))
    return merged


def build_messages(
    history: list[HistoryItem], current_message_id: int, current_text: str
) -> list[ChatMessage] | None:
    if not history:
        return [ChatMessage(role="user", content=current_text)]
    if history[-1].role != "them":
        return None
    background = history[:-1] if history[-1].message_id == current_message_id else history
    merged = _merge_background(background)
    while merged and merged[0].role != "user":
        merged.pop(0)
    merged.append(ChatMessage(role="user", content=current_text))
    return merged


class LLMStep:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def handle(self, ctx: Context) -> None:
        if ctx.stop or ctx.reply is not None:
            return
        messages = build_messages(ctx.history, ctx.msg.message_id, ctx.msg.text or "")
        if messages is None:
            ctx.stop = True
            return
        system = ctx.system.strip()
        system = f"{system}\n\n{LAST_MESSAGE_RULE}" if system else LAST_MESSAGE_RULE
        reply = await self.provider.generate(system, messages)
        finish_reason = getattr(self.provider, "last_finish_reason", None)
        if reply is None:
            logger.warning(
                "escalate",
                extra={
                    "chat_id": ctx.msg.chat_id,
                    "message_id": ctx.msg.message_id,
                    "escalate_reason": "empty_other",
                    "finish_reason": finish_reason,
                },
            )
            ctx.action = Action.ESCALATE
            ctx.reply = None
            return
        text = reply.strip()
        if not text:
            logger.warning(
                "escalate",
                extra={
                    "chat_id": ctx.msg.chat_id,
                    "message_id": ctx.msg.message_id,
                    "escalate_reason": "empty_length",
                    "finish_reason": finish_reason,
                },
            )
            ctx.action = Action.ESCALATE
            ctx.reply = None
            return
        if ESCALATE_TOKEN in text:
            logger.info(
                "escalate",
                extra={
                    "chat_id": ctx.msg.chat_id,
                    "message_id": ctx.msg.message_id,
                    "escalate_reason": "model_token",
                },
            )
            ctx.action = Action.ESCALATE
            ctx.reply = None
            return
        ctx.reply = text
        ctx.action = Action.REPLY
