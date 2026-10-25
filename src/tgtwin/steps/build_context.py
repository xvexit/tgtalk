from __future__ import annotations

import hashlib
from pathlib import Path

from tgtwin.core.models import Context
from tgtwin.core.protocols import MessageRepository


def load_persona(path: str) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    return p.read_text(encoding="utf-8")


class BuildContextStep:
    def __init__(self, repo: MessageRepository, persona: str, history_limit: int = 30) -> None:
        self.repo = repo
        self.persona = persona
        self.history_limit = history_limit

    async def handle(self, ctx: Context) -> None:
        ctx.history = await self.repo.last(ctx.msg.chat_id, self.history_limit)
        ctx.system = self.persona
        ctx.meta["system_hash"] = hashlib.sha256(self.persona.encode("utf-8")).hexdigest()
        ctx.meta["history_ids"] = [h.message_id for h in ctx.history]
