from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tgtwin.eval.models import EvalCase, EvalMessage
from tgtwin.eval.runner import (
    CaseHistoryRepository,
    build_history,
    build_incoming,
    generate_case,
)
from tgtwin.llm.fake import FakeLLMProvider

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def make_case(context_size: int = 2) -> EvalCase:
    context = tuple(
        EvalMessage(1, index, "owner" if index % 2 else "them", f"фон {index}", BASE)
        for index in range(1, context_size + 1)
    )
    return EvalCase(
        chat_id=1,
        trigger=EvalMessage(1, 100, "them", "как дела?", BASE),
        context=context,
        reference_messages=(EvalMessage(1, 101, "owner", "нормально", BASE),),
    )


def test_build_history_and_incoming() -> None:
    case = make_case(context_size=2)
    history = build_history(case)
    assert [item.message_id for item in history] == [1, 2, 100]
    assert history[-1].role == "them"
    incoming = build_incoming(case)
    assert incoming.chat_id == 1
    assert incoming.message_id == 100
    assert incoming.text == "как дела?"
    assert incoming.from_owner is False


@pytest.mark.asyncio
async def test_case_history_repository_truncates_to_last_n() -> None:
    repo = CaseHistoryRepository(build_history(make_case(context_size=3)))
    assert [item.message_id for item in await repo.last(1, 2)] == [3, 100]
    assert await repo.last(1, 0) == []


@pytest.mark.asyncio
async def test_generate_case_uses_prod_pipeline_and_splits_series() -> None:
    result = await generate_case(
        make_case(),
        FakeLLMProvider("Привет!\nКак дела?"),
        system="персона",
        history_limit=30,
    )
    assert result.escalated is False
    assert result.bot == "Привет!\nКак дела?"
    assert result.error is None


@pytest.mark.asyncio
async def test_generate_case_marks_empty_provider_answer_as_escalation() -> None:
    result = await generate_case(
        make_case(),
        FakeLLMProvider(None),
        system="персона",
        history_limit=30,
    )
    assert result.escalated is True
    assert result.bot == ""


@pytest.mark.asyncio
async def test_generate_case_escalates_on_link() -> None:
    result = await generate_case(
        make_case(),
        FakeLLMProvider("смотри https://example.com"),
        system="персона",
        history_limit=30,
    )
    assert result.escalated is True
