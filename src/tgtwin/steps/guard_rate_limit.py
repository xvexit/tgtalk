from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from tgtwin.core.models import Action, Context
from tgtwin.core.protocols import ReplyLogRepository

logger = logging.getLogger(__name__)


class GuardRateLimitStep:
    def __init__(self, log_repo: ReplyLogRepository, max_per_hour: int = 10) -> None:
        self.log_repo = log_repo
        self.max_per_hour = max_per_hour

    async def handle(self, ctx: Context) -> None:
        if ctx.msg.from_owner or self.max_per_hour <= 0:
            return
        since = datetime.now(UTC) - timedelta(hours=1)
        sent = await self.log_repo.count_sent_since(ctx.msg.chat_id, since)
        if sent >= self.max_per_hour:
            logger.warning(
                "rate_limit_replies_exceeded",
                extra={
                    "chat_id": ctx.msg.chat_id,
                    "sent_last_hour": sent,
                    "limit": self.max_per_hour,
                },
            )
            ctx.stop = True
            ctx.action = Action.NONE
