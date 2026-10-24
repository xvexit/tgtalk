from __future__ import annotations

from tgtwin.core.models import Context


class GuardOwnerStep:
    async def handle(self, ctx: Context) -> None:
        if ctx.msg.from_owner:
            ctx.stop = True
