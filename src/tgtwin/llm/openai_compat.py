from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from tgtwin.core.models import ChatMessage
from tgtwin.core.protocols import LLMProvider

logger = logging.getLogger(__name__)


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        http_client: Any | None = None,
        max_tokens: int = 800,
        thinking_enabled: bool = False,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.thinking_enabled = thinking_enabled
        self.last_finish_reason: str | None = None
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            http_client=http_client,
        )

    async def generate(self, system: str, messages: list[ChatMessage]) -> str | None:
        payload: list[dict[str, str]] = []
        if system.strip():
            payload.append({"role": "system", "content": system})
        payload.extend({"role": m.role, "content": m.content} for m in messages)
        extra_body = None
        if not self.thinking_enabled:
            extra_body = {"thinking": {"type": "disabled"}}
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=payload,
            max_tokens=self.max_tokens,
            extra_body=extra_body,
        )
        choice = resp.choices[0]
        self.last_finish_reason = getattr(choice, "finish_reason", None)
        return choice.message.content
