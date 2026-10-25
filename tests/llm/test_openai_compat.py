from __future__ import annotations

import json

import httpx2
import pytest
from openai import APITimeoutError, InternalServerError

from tgtwin.core.models import ChatMessage
from tgtwin.llm.openai_compat import LLM_MAX_TOKENS, OpenAICompatProvider


def make_provider(handler) -> OpenAICompatProvider:
    transport = httpx2.MockTransport(handler)
    client = httpx2.AsyncClient(transport=transport)
    return OpenAICompatProvider(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
        timeout=5.0,
        http_client=client,
    )


async def test_generate_returns_content() -> None:
    async def handler(request):
        return httpx2.Response(
            200, request=request, json={"choices": [{"message": {"content": "привет"}}]}
        )

    provider = make_provider(handler)
    result = await provider.generate(
        "ты — владелец", [ChatMessage(role="user", content="как дела")]
    )
    assert result == "привет"


async def test_payload_roles_and_system() -> None:
    captured = {}

    async def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx2.Response(
            200, request=request, json={"choices": [{"message": {"content": "ок"}}]}
        )

    provider = make_provider(handler)
    await provider.generate(
        "system prompt",
        [
            ChatMessage(role="user", content="вопрос"),
            ChatMessage(role="assistant", content="ответ"),
        ],
    )
    body = captured["body"]
    assert body["model"] == "test-model"
    assert body["max_tokens"] == LLM_MAX_TOKENS
    assert body["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "вопрос"},
        {"role": "assistant", "content": "ответ"},
    ]


async def test_empty_system_omitted() -> None:
    captured = {}

    async def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx2.Response(
            200, request=request, json={"choices": [{"message": {"content": "ок"}}]}
        )

    provider = make_provider(handler)
    await provider.generate("   ", [ChatMessage(role="user", content="вопрос")])
    assert captured["body"]["messages"] == [{"role": "user", "content": "вопрос"}]


async def test_empty_content_returns_empty() -> None:
    async def handler(request):
        return httpx2.Response(200, request=request, json={"choices": [{"message": {"content": None}}]})

    provider = make_provider(handler)
    result = await provider.generate("s", [ChatMessage(role="user", content="вопрос")])
    assert result == ""


async def test_api_error_propagates() -> None:
    async def handler(request):
        return httpx2.Response(500, request=request, json={"error": {"message": "boom"}})

    provider = make_provider(handler)
    with pytest.raises(InternalServerError):
        await provider.generate("s", [ChatMessage(role="user", content="вопрос")])


async def test_timeout_propagates() -> None:
    async def handler(request):
        raise httpx2.ReadTimeout("slow")

    provider = make_provider(handler)
    with pytest.raises(APITimeoutError):
        await provider.generate("s", [ChatMessage(role="user", content="вопрос")])
