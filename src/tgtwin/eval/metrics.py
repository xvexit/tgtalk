from __future__ import annotations

import bisect
import statistics
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from tgtwin.eval.filters import normalize_text
from tgtwin.eval.models import CaseResult
from tgtwin.style.stats import LAUGHTER_PATTERN, extract_emojis

SHORT_REPLIES = frozenset(
    {
        "ага",
        "да",
        "конечно",
        "лол",
        "нет",
        "неа",
        "ну",
        "норм",
        "ок",
        "окей",
        "понял",
        "поняла",
        "привет",
        "спасибо",
        "угу",
        "хз",
        "ясно",
    }
)


def load_profanity(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        raise FileNotFoundError(path)
    words = []
    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.strip().casefold()
        if word and not word.startswith("#"):
            words.append(word)
    return tuple(words)


def compute_metrics(
    results: Sequence[CaseResult],
    *,
    judge_enabled: bool,
    profanity_words: Sequence[str] = (),
) -> dict[str, Any]:
    total = len(results)
    valid = [result for result in results if not result.escalated and result.bot.strip()]
    bot_lengths = [len(normalize_text(result.bot)) for result in valid]
    reference_lengths = [len(normalize_text(result.case.reference)) for result in valid]
    judge = _judge_metrics(results, judge_enabled)

    return {
        "cases": total,
        "valid_share": _ratio(len(valid), total),
        "nonempty_share": _ratio(
            sum(1 for result in results if result.bot.strip()), total
        ),
        "no_escalation_share": _ratio(
            sum(1 for result in results if not result.escalated), total
        ),
        "length": {
            "bot_median": _median(bot_lengths),
            "reference_median": _median(reference_lengths),
            "ks": _ks_distance(bot_lengths, reference_lengths),
        },
        "style": {
            "bot": _style_shares([result.bot for result in valid], profanity_words),
            "reference": _style_shares(
                [result.case.reference for result in valid], profanity_words
            ),
        },
        "reply_count": {
            "bot_mean": _mean([len(_lines(result.bot)) for result in results]),
            "reference_mean": _mean([result.case.reference_count for result in results]),
            "bot_histogram": _reply_histogram(
                [len(_lines(result.bot)) for result in results]
            ),
        },
        "short_match_share": _ratio(
            sum(1 for result in results if _short_match(result)), total
        ),
        "judge": judge,
    }


def _judge_metrics(results: Sequence[CaseResult], enabled: bool) -> dict[str, Any] | None:
    if not enabled:
        return None
    valid = [result for result in results if result.judge_choice in {"A", "B"}]
    invalid = len(results) - len(valid)
    invalid_share = _ratio(invalid, len(results))
    return {
        "valid": len(valid),
        "invalid": invalid,
        "invalid_share": invalid_share,
        "failed": bool(invalid_share is not None and invalid_share > 0.10),
        "accuracy": _ratio(sum(1 for result in valid if result.judge_correct), len(valid)),
        "a_share": _ratio(
            sum(1 for result in valid if result.judge_choice == "A"), len(valid)
        ),
    }


def _style_shares(texts: Sequence[str], profanity_words: Sequence[str]) -> dict[str, Any]:
    total = len(texts)
    return {
        "lowercase_start": _ratio(_lowercase_count(texts), total),
        "no_terminal_dot": _ratio(
            sum(1 for text in texts if _no_terminal_dot(text)), total
        ),
        "emoji": _ratio(sum(1 for text in texts if extract_emojis(text)), total),
        "laughter": _ratio(
            sum(1 for text in texts if LAUGHTER_PATTERN.search(text)), total
        ),
        "profanity": _ratio(
            sum(1 for text in texts if _has_profanity(text, profanity_words)), total
        ),
    }


def _short_match(result: CaseResult) -> bool:
    bot_lines = _short_lines(result.bot)
    if not bot_lines:
        return False
    reference_lines = _short_lines(result.case.reference)
    return bool(bot_lines & reference_lines)


def _short_lines(text: str) -> set[str]:
    return {
        normalize_text(line).casefold()
        for line in text.splitlines()
        if normalize_text(line).casefold() in SHORT_REPLIES
    }


def _lowercase_count(texts: Sequence[str]) -> int:
    matched = 0
    for text in texts:
        first = next((char for char in text if char.isalpha()), None)
        if first is not None and not first.isupper():
            matched += 1
    return matched


def _no_terminal_dot(text: str) -> bool:
    value = text.rstrip()
    return bool(value) and not value.endswith(".")


def _has_profanity(text: str, words: Sequence[str]) -> bool:
    folded = text.casefold()
    return any(word in folded for word in words)


def _lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _reply_histogram(counts: Sequence[int]) -> dict[str, int]:
    counter = Counter(min(count, 3) for count in counts)
    return {str(index): counter.get(index, 0) for index in range(4)}


def _median(values: Sequence[int]) -> float | None:
    return float(statistics.median(values)) if values else None


def _mean(values: Sequence[int]) -> float | None:
    return sum(values) / len(values) if values else None


def _ratio(matched: int, total: int) -> float | None:
    return matched / total if total else None


def _ks_distance(left: Sequence[int], right: Sequence[int]) -> float | None:
    if not left or not right:
        return None
    left_sorted = sorted(left)
    right_sorted = sorted(right)
    values = sorted(set(left_sorted) | set(right_sorted))
    distance = 0.0
    for value in values:
        left_cdf = bisect.bisect_right(left_sorted, value) / len(left_sorted)
        right_cdf = bisect.bisect_right(right_sorted, value) / len(right_sorted)
        distance = max(distance, abs(left_cdf - right_cdf))
    return distance
