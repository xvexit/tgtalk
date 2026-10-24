from __future__ import annotations

from tgtwin.core.models import ChatMessage
from tgtwin.core.protocols import LLMProvider


class FakeLLMProvider(LLMProvider):
    def __init__(self, response: str = "Привет, как дела?") -> None:
        self.response = response

    async def generate(self, system: str, messages: list[ChatMessage]) -> str:
        return self.response
