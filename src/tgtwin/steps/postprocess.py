from __future__ import annotations

from tgtwin.core.models import Context


class PostprocessStep:
    async def handle(self, ctx: Context) -> None:
        if ctx.reply:
            ctx.reply = ctx.reply.strip()
