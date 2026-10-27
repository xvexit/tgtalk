from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tgtwin.core.models import ChatMessage
from tgtwin.eval.judge import DeepSeekJudge, build_judge_prompt
from tgtwin.eval.models import EvalCase, EvalMessage

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def make_case() -> EvalCase:
    return EvalCase(
        chat_id=1,
        trigger=EvalMessage(1, 2, "them", "как дела?", BASE),
        context=(EvalMessage(1, 1, "owner", "привет", BASE),),
        reference_messages=(EvalMessage(1, 3, "owner", "нормально", BASE),),
    )


class StubProvider:
    def __init__(self, response: str | None) -> None:
        self.response = response
        self.system = ""
        self.messages: list[ChatMessage] = []

    async def generate(self, system: str, messages: list[ChatMessage]) -> str | None:
        self.system = system
        self.messages = messages
        return self.response


def test_build_judge_prompt_contains_context_trigger_and_answers() -> None:
    prompt = build_judge_prompt(make_case(), "вариант а", "вариант б")
    assert "Владелец: привет" in prompt
    assert "Собеседник: как дела?" in prompt
    assert "Вариант A:\nвариант а" in prompt
    assert "Вариант B:\nвариант б" in prompt


@pytest.mark.asyncio
async def test_deepseek_judge_parses_choice() -> None:
    provider = StubProvider("Ответ: B")
    judge = DeepSeekJudge(provider)
    choice = await judge.choose(make_case(), "а", "б")
    assert choice == "B"
    assert provider.messages[0].role == "user"


@pytest.mark.asyncio
async def test_deepseek_judge_returns_none_for_unparsable_answer() -> None:
    judge = DeepSeekJudge(StubProvider("не знаю"))
    assert await judge.choose(make_case(), "а", "б") is None


@pytest.mark.asyncio
async def test_deepseek_judge_returns_none_for_empty_provider_answer() -> None:
    judge = DeepSeekJudge(StubProvider(None))
    assert await judge.choose(make_case(), "а", "б") is None
