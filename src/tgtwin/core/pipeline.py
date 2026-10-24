from __future__ import annotations

import logging

from .models import Action, Context
from .protocols import Step

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(self, steps: list[Step]) -> None:
        self.steps = steps

    async def run(self, ctx: Context) -> Context:
        for step in self.steps:
            if ctx.stop:
                ctx.meta.setdefault("stopped_by", getattr(step, "__class__", type(step)).__name__)
                break
            step_name = step.__class__.__name__
            try:
                await step.handle(ctx)
            except Exception:
                logger.exception(
                    "step_failed",
                    extra={
                        "step": step_name,
                        "chat_id": ctx.msg.chat_id,
                        "message_id": ctx.msg.message_id,
                    },
                )
                ctx.stop = True
                ctx.action = Action.NONE
                ctx.reply = None
                ctx.meta["error"] = step_name
                break
            if ctx.stop:
                ctx.meta.setdefault("stopped_by", step_name)
                break
        return ctx
