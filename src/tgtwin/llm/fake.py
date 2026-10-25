from __future__ import annotations

from tgtwin.core.models import ChatMessage
from tgtwin.core.protocols import LLMProvider


class FakeLLMProvider(LLMProvider):
    def __init__(self, response: str | None = "Привет, как дела?") -> None:
        self.response = response
        self.last_finish_reason: str | None = None

    async def generate(self, system: str, messages: list[ChatMessage]) -> str | None:
        return self.response
