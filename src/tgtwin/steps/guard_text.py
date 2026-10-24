from __future__ import annotations

from tgtwin.core.models import Context


class GuardTextStep:
    async def handle(self, ctx: Context) -> None:
        if not ctx.msg.text:
            ctx.stop = True
