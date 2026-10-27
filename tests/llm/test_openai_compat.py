from __future__ import annotations

import json

import httpx2
import pytest
from openai import APITimeoutError, InternalServerError

from tgtwin.core.models import ChatMessage
from tgtwin.llm.openai_compat import OpenAICompatProvider


def make_provider(handler, thinking_enabled: bool = False, max_tokens: int = 800) -> OpenAICompatProvider:
    transport = httpx2.MockTransport(handler)
    client = httpx2.AsyncClient(transport=transport)
    return OpenAICompatProvider(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
        timeout=5.0,
        http_client=client,
        thinking_enabled=thinking_enabled,
        max_tokens=max_tokens,
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


async def test_payload_roles_system_max_tokens_and_thinking_disabled() -> None:
    captured = {}

    async def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx2.Response(
            200, request=request, json={"choices": [{"message": {"content": "ок"}}]}
        )

    provider = make_provider(handler, max_tokens=512)
    await provider.generate(
        "system prompt",
        [
            ChatMessage(role="user", content="вопрос"),
            ChatMessage(role="assistant", content="ответ"),
        ],
    )
    body = captured["body"]
    assert body["model"] == "test-model"
    assert body["max_tokens"] == 512
    assert body["thinking"] == {"type": "disabled"}
    assert body["messages"] == [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "вопрос"},
        {"role": "assistant", "content": "ответ"},
    ]


async def test_thinking_enabled_omits_disabled_body() -> None:
    captured = {}

    async def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx2.Response(
            200, request=request, json={"choices": [{"message": {"content": "ок"}}]}
        )

    provider = make_provider(handler, thinking_enabled=True)
    await provider.generate("s", [ChatMessage(role="user", content="вопрос")])
    assert "thinking" not in captured["body"]


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


async def test_none_content_returns_none_and_finish_reason_saved() -> None:
    async def handler(request):
        return httpx2.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": None}, "finish_reason": "length"}]},
        )

    provider = make_provider(handler)
    result = await provider.generate("s", [ChatMessage(role="user", content="вопрос")])
    assert result is None
    assert provider.last_finish_reason == "length"


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


async def test_temperature_passed_when_configured() -> None:
    captured = {}

    async def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx2.Response(
            200, request=request, json={"choices": [{"message": {"content": "A"}}]}
        )

    transport = httpx2.MockTransport(handler)
    client = httpx2.AsyncClient(transport=transport)
    provider = OpenAICompatProvider(
        api_key="test-key",
        base_url="https://example.com/v1",
        model="test-model",
        timeout=5.0,
        http_client=client,
        temperature=0.0,
    )
    await provider.generate("s", [ChatMessage(role="user", content="вопрос")])
    assert captured["body"]["temperature"] == 0.0


async def test_temperature_omitted_by_default() -> None:
    captured = {}

    async def handler(request):
        captured["body"] = json.loads(request.content)
        return httpx2.Response(
            200, request=request, json={"choices": [{"message": {"content": "A"}}]}
        )

    provider = make_provider(handler)
    await provider.generate("s", [ChatMessage(role="user", content="вопрос")])
    assert "temperature" not in captured["body"]
