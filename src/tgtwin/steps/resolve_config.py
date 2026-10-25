from __future__ import annotations

from tgtwin.core.models import Context, Mode, ResolvedConfig


class ResolveConfigStep:
    def __init__(self, default_mode: Mode = Mode.DRY_RUN) -> None:
        self.default_mode = default_mode

    async def handle(self, ctx: Context) -> None:
        if ctx.cfg is None:
            ctx.cfg = ResolvedConfig(mode=self.default_mode)
