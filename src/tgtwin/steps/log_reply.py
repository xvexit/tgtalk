from __future__ import annotations

from tgtwin.core.models import Context, ReplyLogEntry
from tgtwin.core.protocols import ReplyLogRepository


class LogReplyStep:
    def __init__(self, log_repo: ReplyLogRepository, model: str) -> None:
        self.log_repo = log_repo
        self.model = model

    async def handle(self, ctx: Context) -> None:
        entry = ReplyLogEntry(
            chat_id=ctx.msg.chat_id,
            trigger_message_id=ctx.msg.message_id,
            mode=ctx.cfg.mode.value if ctx.cfg else "dry_run",
            reply=ctx.reply,
            sent=False,
            context={
                "history_ids": ctx.meta.get("history_ids", []),
                "system_hash": ctx.meta.get("system_hash", ""),
                "model": self.model,
            },
        )
        log_id = await self.log_repo.add(entry)
        ctx.meta["reply_log_id"] = log_id
