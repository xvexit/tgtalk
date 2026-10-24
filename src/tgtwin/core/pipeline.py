from __future__ import annotations

from .models import Context
from .protocols import Step


class Pipeline:
    def __init__(self, steps: list[Step]) -> None:
        self.steps = steps

    async def run(self, ctx: Context) -> Context:
        for step in self.steps:
            if ctx.stop:
                break
            await step.handle(ctx)
            if ctx.stop:
                break
        return ctx
