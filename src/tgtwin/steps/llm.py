from __future__ import annotations

from tgtwin.core.models import Action, ChatMessage, Context
from tgtwin.core.protocols import LLMProvider


class LLMStep:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def handle(self, ctx: Context) -> None:
        if ctx.stop or ctx.reply is not None:
            return
        messages = [ChatMessage(role="user", content=ctx.msg.text or "")]
        reply = await self.provider.generate(ctx.system, messages)
        ctx.reply = reply
        ctx.action = Action.REPLY
