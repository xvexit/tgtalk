from __future__ import annotations

import logging
import random
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal, cast

from tgtwin.core.models import Action, Context, HistoryItem, IncomingMessage
from tgtwin.core.pipeline import Pipeline
from tgtwin.core.protocols import LLMProvider, MessageRepository
from tgtwin.eval.judge import Judge
from tgtwin.eval.models import CaseResult, EvalCase
from tgtwin.steps.build_context import BuildContextStep
from tgtwin.steps.llm import LLMStep
from tgtwin.steps.postprocess import PostprocessStep

logger = logging.getLogger(__name__)


class CaseHistoryRepository:
    def __init__(self, history: Sequence[HistoryItem]) -> None:
        self.history = list(history)

    async def last(self, chat_id: int, n: int) -> list[HistoryItem]:
        return self.history[-n:] if n > 0 else []


def build_history(case: EvalCase) -> list[HistoryItem]:
    items = [
        HistoryItem(
            message_id=message.message_id,
            role=_history_role(message.role),
            text=message.text,
            ts=_aware(message.ts),
        )
        for message in case.context
    ]
    items.append(
        HistoryItem(
            message_id=case.trigger.message_id,
            role="them",
            text=case.trigger.text,
            ts=_aware(case.trigger.ts),
        )
    )
    return items


def build_incoming(case: EvalCase) -> IncomingMessage:
    return IncomingMessage(
        channel="eval",
        connection_id="",
        chat_id=case.chat_id,
        message_id=case.trigger.message_id,
        text=case.trigger.text,
        from_owner=False,
        ts=_aware(case.trigger.ts),
    )


async def generate_case(
    case: EvalCase,
    provider: LLMProvider,
    *,
    system: str,
    history_limit: int,
) -> CaseResult:
    history_repo = CaseHistoryRepository(build_history(case))
    pipeline = Pipeline(
        [
            BuildContextStep(
                cast(MessageRepository, history_repo),
                system,
                history_limit=history_limit,
            ),
            LLMStep(provider),
            PostprocessStep(),
        ]
    )
    ctx = Context(msg=build_incoming(case))
    await pipeline.run(ctx)
    error = ctx.meta.get("error")
    return CaseResult(
        case=case,
        bot=ctx.reply or "",
        escalated=ctx.action == Action.ESCALATE,
        error=str(error) if error is not None else None,
    )


async def run_cases(
    cases: Sequence[EvalCase],
    provider: LLMProvider,
    *,
    system: str,
    history_limit: int,
) -> list[CaseResult]:
    results: list[CaseResult] = []
    for case in cases:
        results.append(
            await generate_case(
                case,
                provider,
                system=system,
                history_limit=history_limit,
            )
        )
    return results


async def run_judge(
    results: Sequence[CaseResult],
    judge: Judge,
    *,
    seed: int,
) -> None:
    rng = random.Random(seed)
    for result in results:
        a_is_reference = rng.random() < 0.5
        answer_a = result.case.reference if a_is_reference else result.bot
        answer_b = result.bot if a_is_reference else result.case.reference
        result.judge_a_is_reference = a_is_reference
        try:
            choice = await judge.choose(result.case, answer_a, answer_b)
        except Exception:
            logger.exception(
                "eval_judge_failed",
                extra={
                    "chat_id": result.case.chat_id,
                    "message_id": result.case.trigger.message_id,
                },
            )
            choice = None
        result.judge_choice = choice
        if choice in {"A", "B"}:
            result.judge_correct = (choice == "A") == a_is_reference


def _history_role(role: str) -> Literal["them", "owner", "bot"]:
    return cast(
        Literal["them", "owner", "bot"],
        role if role in {"them", "owner", "bot"} else "them",
    )


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
