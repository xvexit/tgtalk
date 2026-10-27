from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta

from tgtwin.eval.filters import has_sensitive, leaks_persona
from tgtwin.eval.models import EvalCase, EvalMessage, SelectionStats

DEFERRED_FRACTION = 0.15
MAX_WAIT = timedelta(minutes=10)
MAX_GAP = timedelta(minutes=2)


def split_deferred(
    messages: Sequence[EvalMessage],
    fraction: float = DEFERRED_FRACTION,
) -> tuple[list[EvalMessage], list[EvalMessage], datetime | None]:
    ordered = sorted(messages, key=lambda item: (item.ts, item.message_id))
    if not ordered:
        return [], [], None
    deferred_count = max(1, math.ceil(len(ordered) * fraction))
    cutoff_ts = ordered[len(ordered) - deferred_count].ts
    deferred = [message for message in ordered if message.ts >= cutoff_ts]
    return ordered, deferred, cutoff_ts


def owner_series(
    ordered: Sequence[EvalMessage],
    trigger_index: int,
    *,
    max_wait: timedelta = MAX_WAIT,
    max_gap: timedelta = MAX_GAP,
) -> list[EvalMessage]:
    trigger = ordered[trigger_index]
    next_index = trigger_index + 1
    if next_index >= len(ordered):
        return []
    first = ordered[next_index]
    if first.role != "owner" or first.ts - trigger.ts > max_wait:
        return []
    series = [first]
    previous = first
    for message in ordered[next_index + 1 :]:
        if message.role != "owner":
            break
        if message.ts - previous.ts > max_gap:
            break
        series.append(message)
        previous = message
    return series


def select_cases(
    messages_by_chat: Mapping[int, Sequence[EvalMessage]],
    *,
    persona_text: str,
    history_limit: int,
    cases: int,
    seed: int,
) -> tuple[list[EvalCase], SelectionStats]:
    stats = SelectionStats()
    candidates: list[EvalCase] = []
    context_size = max(0, history_limit - 1)

    for chat_id in sorted(messages_by_chat):
        messages = messages_by_chat[chat_id]
        stats.loaded_messages += len(messages)
        chat_counts = {
            "loaded_messages": len(messages),
            "deferred_messages": 0,
            "trigger_candidates": 0,
            "with_series": 0,
            "selected": 0,
        }
        ordered, deferred, cutoff_ts = split_deferred(messages)
        stats.deferred_messages += len(deferred)
        chat_counts["deferred_messages"] = len(deferred)
        if cutoff_ts is None:
            stats.per_chat[chat_id] = chat_counts
            continue

        for index, message in enumerate(ordered):
            if message.role != "them" or message.ts < cutoff_ts or not message.text.strip():
                continue
            stats.trigger_candidates += 1
            chat_counts["trigger_candidates"] += 1
            series = owner_series(ordered, index)
            if not series:
                continue
            stats.with_series += 1
            chat_counts["with_series"] += 1
            context = tuple(ordered[max(0, index - context_size) : index])
            candidates.append(
                EvalCase(
                    chat_id=chat_id,
                    trigger=message,
                    context=context,
                    reference_messages=tuple(series),
                )
            )
        stats.per_chat[chat_id] = chat_counts

    after_sensitive: list[EvalCase] = []
    for case in candidates:
        texts = [case.reference, case.trigger.text]
        texts.extend(message.text for message in case.context)
        if any(has_sensitive(text) for text in texts):
            continue
        after_sensitive.append(case)
    stats.after_sensitive = len(after_sensitive)

    after_persona = [
        case for case in after_sensitive if not leaks_persona(case.reference, persona_text)
    ]
    stats.after_persona = len(after_persona)

    rng = random.Random(seed)
    rng.shuffle(after_persona)
    selected = after_persona[: max(0, cases)]
    stats.selected = len(selected)
    for case in selected:
        stats.per_chat.setdefault(case.chat_id, {})["selected"] = (
            stats.per_chat.get(case.chat_id, {}).get("selected", 0) + 1
        )
    return selected, stats
