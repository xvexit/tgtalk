from __future__ import annotations

from datetime import datetime, timedelta, timezone

from tgtwin.core.models import Context
from tgtwin.core.protocols import MessageRepository


class GuardTakeoverStep:
    def __init__(self, repo: MessageRepository, default_hours: int = 3) -> None:
        self.repo = repo
        self.default_hours = default_hours

    async def handle(self, ctx: Context) -> None:
        if ctx.msg.from_owner:
            return
        hours = self.default_hours
        if ctx.cfg and ctx.cfg.overrides:
            h = ctx.cfg.overrides.get("takeover_hours")
            if isinstance(h, int):
                hours = h
        last = await self.repo.last_owner_ts(ctx.msg.chat_id)
        if last is None:
            return
        now = datetime.now(timezone.utc)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last < timedelta(hours=hours):
            ctx.stop = True
