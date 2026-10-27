from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tgtwin.eval.models import EvalMessage
from tgtwin.eval.sampling import owner_series, select_cases, split_deferred

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def msg(index: int, role: str, text: str, minute: int | None = None) -> EvalMessage:
    return EvalMessage(
        chat_id=1,
        message_id=index,
        role=role,
        text=text,
        ts=BASE + timedelta(minutes=minute if minute is not None else index),
    )


def make_chat() -> list[EvalMessage]:
    messages = [msg(index, "them" if index % 2 == 0 else "owner", f"текст {index}") for index in range(17)]
    messages.append(msg(17, "them", "вопрос"))
    messages.append(msg(18, "owner", "ответ один"))
    messages.append(msg(19, "owner", "ответ два"))
    return messages


def test_split_deferred_uses_last_fifteen_percent() -> None:
    messages = [msg(index, "them", f"t{index}") for index in range(10)]
    ordered, deferred, cutoff = split_deferred(messages)
    assert len(ordered) == 10
    assert len(deferred) == 2
    assert cutoff == messages[8].ts
    assert [item.message_id for item in deferred] == [8, 9]


def test_owner_series_collects_immediate_owner_messages() -> None:
    messages = [
        msg(0, "them", "вопрос"),
        msg(1, "owner", "раз", 1),
        msg(2, "owner", "два", 2),
        msg(3, "owner", "три", 5),
    ]
    assert [item.message_id for item in owner_series(messages, 0)] == [1, 2]


def test_owner_series_requires_owner_soon_after_trigger() -> None:
    messages = [msg(0, "them", "вопрос"), msg(1, "owner", "ответ", 11)]
    assert owner_series(messages, 0) == []


def test_owner_series_stops_when_other_role_appears() -> None:
    messages = [
        msg(0, "them", "вопрос"),
        msg(1, "owner", "ответ", 1),
        msg(2, "them", "ещё вопрос", 2),
        msg(3, "owner", "ответ", 3),
    ]
    assert [item.message_id for item in owner_series(messages, 0)] == [1]


def test_select_cases_builds_case_with_context_and_reference() -> None:
    cases, stats = select_cases(
        {1: make_chat()},
        persona_text="совсем другая персона",
        history_limit=3,
        cases=10,
        seed=1,
    )
    assert len(cases) == 1
    assert stats.loaded_messages == 20
    assert stats.selected == 1
    case = cases[0]
    assert case.trigger.message_id == 17
    assert [item.message_id for item in case.context] == [15, 16]
    assert [item.message_id for item in case.reference_messages] == [18, 19]
    assert case.reference == "ответ один\nответ два"


def test_select_cases_filters_sensitive_context() -> None:
    messages = make_chat()
    messages[16] = msg(16, "owner", "смотри https://example.com")
    cases, stats = select_cases(
        {1: messages},
        persona_text="совсем другая персона",
        history_limit=30,
        cases=10,
        seed=1,
    )
    assert cases == []
    assert stats.with_series == 1
    assert stats.after_sensitive == 0


def test_select_cases_filters_sensitive_reference() -> None:
    messages = make_chat()
    messages[18] = msg(18, "owner", "звони +7 (999) 123-45-67")
    cases, stats = select_cases(
        {1: messages},
        persona_text="совсем другая персона",
        history_limit=30,
        cases=10,
        seed=1,
    )
    assert cases == []
    assert stats.after_sensitive == 0


def test_select_cases_filters_persona_leak() -> None:
    messages = make_chat()
    persona = "ответ один ответ два"
    cases, stats = select_cases(
        {1: messages},
        persona_text=persona,
        history_limit=30,
        cases=10,
        seed=1,
    )
    assert cases == []
    assert stats.after_sensitive == 1
    assert stats.after_persona == 0


def test_select_cases_is_deterministic_and_honors_limit() -> None:
    messages = make_chat()
    messages.extend(
        [
            msg(20, "them", "вопрос два"),
            msg(21, "owner", "ответ три"),
        ]
    )
    first, _ = select_cases(
        {1: messages},
        persona_text="совсем другая персона",
        history_limit=30,
        cases=1,
        seed=7,
    )
    second, stats = select_cases(
        {1: messages},
        persona_text="совсем другая персона",
        history_limit=30,
        cases=1,
        seed=7,
    )
    assert [case.trigger.message_id for case in first] == [
        case.trigger.message_id for case in second
    ]
    assert stats.selected == 1
