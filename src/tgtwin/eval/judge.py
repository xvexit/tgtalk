from __future__ import annotations

import re
from typing import Protocol

from tgtwin.core.models import ChatMessage
from tgtwin.core.protocols import LLMProvider
from tgtwin.eval.models import EvalCase

JUDGE_SYSTEM = (
    "Ты помогаешь оценить, насколько ответ похож на настоящего владельца переписки. "
    "Тебе дан фрагмент диалога и два варианта ответа. Ровно один вариант написал "
    "настоящий владелец, второй сгенерирован. Ответь только одной буквой: A или B."
)
CHOICE_PATTERN = re.compile(r"\b([AB])\b")


class Judge(Protocol):
    async def choose(self, case: EvalCase, answer_a: str, answer_b: str) -> str | None: ...


class DeepSeekJudge:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def choose(self, case: EvalCase, answer_a: str, answer_b: str) -> str | None:
        raw = await self.provider.generate(
            JUDGE_SYSTEM,
            [ChatMessage(role="user", content=build_judge_prompt(case, answer_a, answer_b))],
        )
        if raw is None:
            return None
        match = CHOICE_PATTERN.search(raw.upper())
        return match.group(1) if match else None


def build_judge_prompt(case: EvalCase, answer_a: str, answer_b: str) -> str:
    lines = ["Фрагмент переписки:"]
    for message in case.context:
        lines.append(f"{_role_label(message.role)}: {message.text}")
    lines.append(f"Собеседник: {case.trigger.text}")
    lines.extend(
        [
            "",
            "Вариант A:",
            answer_a,
            "",
            "Вариант B:",
            answer_b,
            "",
            "Какой вариант написал настоящий владелец? Ответь одной буквой A или B.",
        ]
    )
    return "\n".join(lines)


def _role_label(role: str) -> str:
    if role == "owner":
        return "Владелец"
    if role == "bot":
        return "Бот"
    return "Собеседник"
