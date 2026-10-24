from __future__ import annotations

from tgtwin.core.models import Context, Mode, ResolvedConfig


class ResolveConfigStep:
    async def handle(self, ctx: Context) -> None:
        if ctx.cfg is None:
            ctx.cfg = ResolvedConfig(mode=Mode.DRY_RUN)
