from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from tgtwin.eval.metrics import compute_metrics, load_profanity
from tgtwin.eval.models import CaseResult, EvalCase, EvalMessage
from tgtwin.eval.runner import run_judge

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def make_case(reference: str, *, index: int = 1) -> EvalCase:
    trigger = EvalMessage(
        chat_id=1,
        message_id=index,
        role="them",
        text="вопрос",
        ts=BASE,
    )
    references = tuple(
        EvalMessage(
            chat_id=1,
            message_id=index * 10 + offset,
            role="owner",
            text=line,
            ts=BASE,
        )
        for offset, line in enumerate(reference.splitlines())
    )
    return EvalCase(chat_id=1, trigger=trigger, context=(), reference_messages=references)


def make_result(
    bot: str,
    reference: str = "ответ",
    *,
    escalated: bool = False,
    judge_choice: str | None = None,
    judge_correct: bool | None = None,
    index: int = 1,
) -> CaseResult:
    return CaseResult(
        case=make_case(reference, index=index),
        bot=bot,
        escalated=escalated,
        judge_choice=judge_choice,
        judge_correct=judge_correct,
    )


def test_compute_metrics_handles_empty_results() -> None:
    metrics = compute_metrics([], judge_enabled=True)
    assert metrics["cases"] == 0
    assert metrics["valid_share"] is None
    assert metrics["length"]["bot_median"] is None
    assert metrics["judge"]["failed"] is False


def test_compute_metrics_valid_and_escalated() -> None:
    results = [
        make_result("ок", reference="ок", index=1),
        make_result("ответ", reference="ответ", escalated=True, index=2),
        make_result("", reference="ответ", index=3),
    ]
    metrics = compute_metrics(results, judge_enabled=False)
    assert metrics["valid_share"] == pytest.approx(1 / 3)
    assert metrics["no_escalation_share"] == pytest.approx(2 / 3)
    assert metrics["nonempty_share"] == pytest.approx(2 / 3)
    assert metrics["short_match_share"] == pytest.approx(1 / 3)


def test_compute_metrics_style_and_length() -> None:
    references = ["ок", "да", "привет"]
    bots = ["Это сгенерированный ответ.", "Другой сгенерированный ответ.", "Третий ответ."]
    results = [
        make_result(bot, reference=reference, index=index)
        for index, (bot, reference) in enumerate(zip(bots, references, strict=True), 1)
    ]
    metrics = compute_metrics(
        results,
        judge_enabled=False,
        profanity_words=("бля",),
    )
    assert metrics["style"]["bot"]["lowercase_start"] == 0
    assert metrics["style"]["reference"]["lowercase_start"] == 1
    assert metrics["style"]["bot"]["no_terminal_dot"] == 0
    assert metrics["style"]["reference"]["no_terminal_dot"] == 1
    assert metrics["length"]["bot_median"] > metrics["length"]["reference_median"]
    assert metrics["length"]["ks"] > 0.9


def test_judge_metrics_excludes_invalid_and_marks_failed() -> None:
    valid = [
        make_result("a", judge_choice="A", judge_correct=True, index=index)
        for index in range(1, 9)
    ]
    invalid = [
        make_result("b", judge_choice=None, index=index) for index in range(9, 11)
    ]
    metrics = compute_metrics(valid + invalid, judge_enabled=True)
    assert metrics["judge"]["valid"] == 8
    assert metrics["judge"]["invalid"] == 2
    assert metrics["judge"]["invalid_share"] == pytest.approx(0.2)
    assert metrics["judge"]["failed"] is True
    assert metrics["judge"]["accuracy"] == pytest.approx(1.0)
    assert metrics["judge"]["a_share"] == pytest.approx(1.0)


def test_judge_invalid_share_at_ten_percent_is_not_failed() -> None:
    valid = [
        make_result("a", judge_choice="B", judge_correct=False, index=index)
        for index in range(1, 10)
    ]
    invalid = [make_result("b", judge_choice=None, index=10)]
    metrics = compute_metrics(valid + invalid, judge_enabled=True)
    assert metrics["judge"]["invalid"] == 1
    assert metrics["judge"]["invalid_share"] == pytest.approx(0.1)
    assert metrics["judge"]["failed"] is False


class AlwaysFirstJudge:
    async def choose(self, case, answer_a: str, answer_b: str) -> str:
        return "A"


@pytest.mark.asyncio
async def test_always_first_judge_has_chance_accuracy() -> None:
    results = [
        make_result("сгенерированный ответ", reference="настоящий ответ", index=index)
        for index in range(1, 101)
    ]
    await run_judge(results, AlwaysFirstJudge(), seed=1)
    metrics = compute_metrics(results, judge_enabled=True)
    assert metrics["judge"]["accuracy"] is not None
    assert 0.35 <= metrics["judge"]["accuracy"] <= 0.65


def test_load_profanity_ignores_comments_and_empty_lines(tmp_path: Path) -> None:
    path = tmp_path / "profanity.txt"
    path.write_text("# comment\n\nБля\nхуй\n", encoding="utf-8")
    assert load_profanity(path) == ("бля", "хуй")


def test_profanity_share() -> None:
    results = [
        make_result("ну бля, опять", reference="опять", index=1),
        make_result("нормально", reference="нормально", index=2),
    ]
    metrics = compute_metrics(results, judge_enabled=False, profanity_words=("бля",))
    assert metrics["style"]["bot"]["profanity"] == pytest.approx(0.5)
    assert metrics["style"]["reference"]["profanity"] == 0
