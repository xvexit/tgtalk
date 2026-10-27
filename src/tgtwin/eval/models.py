from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class EvalMessage:
    chat_id: int
    message_id: int
    role: str
    text: str
    ts: datetime


@dataclass(frozen=True)
class EvalCase:
    chat_id: int
    trigger: EvalMessage
    context: tuple[EvalMessage, ...]
    reference_messages: tuple[EvalMessage, ...]

    @property
    def reference(self) -> str:
        return "\n".join(message.text.strip() for message in self.reference_messages)

    @property
    def reference_count(self) -> int:
        return len(self.reference_messages)


@dataclass
class CaseResult:
    case: EvalCase
    bot: str
    escalated: bool
    error: str | None = None
    judge_choice: str | None = None
    judge_a_is_reference: bool | None = None
    judge_correct: bool | None = None


@dataclass
class SelectionStats:
    loaded_messages: int = 0
    deferred_messages: int = 0
    trigger_candidates: int = 0
    with_series: int = 0
    after_sensitive: int = 0
    after_persona: int = 0
    selected: int = 0
    per_chat: dict[int, dict[str, int]] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "loaded_messages": self.loaded_messages,
            "deferred_messages": self.deferred_messages,
            "trigger_candidates": self.trigger_candidates,
            "with_series": self.with_series,
            "after_sensitive": self.after_sensitive,
            "after_persona": self.after_persona,
            "selected": self.selected,
            "steps": [
                {
                    "name": "deferred",
                    "before": self.loaded_messages,
                    "after": self.deferred_messages,
                },
                {
                    "name": "trigger_them",
                    "before": self.deferred_messages,
                    "after": self.trigger_candidates,
                },
                {
                    "name": "owner_series",
                    "before": self.trigger_candidates,
                    "after": self.with_series,
                },
                {
                    "name": "sensitive",
                    "before": self.with_series,
                    "after": self.after_sensitive,
                },
                {
                    "name": "persona_leak",
                    "before": self.after_sensitive,
                    "after": self.after_persona,
                },
                {
                    "name": "selected",
                    "before": self.after_persona,
                    "after": self.selected,
                },
            ],
            "per_chat": self.per_chat,
        }
