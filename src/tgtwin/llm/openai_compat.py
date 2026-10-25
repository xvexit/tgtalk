from __future__ import annotations

import logging
from typing import Any

from openai import AsyncOpenAI

from tgtwin.core.models import ChatMessage
from tgtwin.core.protocols import LLMProvider

logger = logging.getLogger(__name__)

LLM_MAX_TOKENS = 800


class OpenAICompatProvider(LLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        timeout: float,
        http_client: Any | None = None,
    ) -> None:
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout,
            http_client=http_client,
        )

    async def generate(self, system: str, messages: list[ChatMessage]) -> str:
        payload: list[dict[str, str]] = []
        if system.strip():
            payload.append({"role": "system", "content": system})
        payload.extend({"role": m.role, "content": m.content} for m in messages)
        resp = await self.client.chat.completions.create(
            model=self.model,
            messages=payload,
            max_tokens=LLM_MAX_TOKENS,
        )
        content = resp.choices[0].message.content
        return content or ""
