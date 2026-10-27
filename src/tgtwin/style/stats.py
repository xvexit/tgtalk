from __future__ import annotations

import math
import random
import re
import statistics
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

URL_PATTERN = re.compile(r"(?i)\b(?:https?://|www\.)\S+")
URI_PATTERN = re.compile(r"\w+://\S+")
EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
TELEGRAM_LINK_PATTERN = re.compile(r"(?i)\b(?:t\.me|telegram\.me)/\S+")
MENTION_PATTERN = re.compile(r"(?<![\w@])@[A-Za-z0-9_]{3,}")
IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"
)
UUID_PATTERN = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
PHONE_PATTERN = re.compile(r"(?<!\w)\+?\d[\d\s().-]{5,}\d(?!\w)")
LONG_TOKEN_PATTERN = re.compile(
    r"(?<!\w)(?=[A-Za-z0-9_=-]{20,}(?!\w))(?=[A-Za-z0-9_=-]*[A-Za-z_=-])[A-Za-z0-9_=-]{20,}(?!\w)"
)
LONG_NUMBER_PATTERN = re.compile(r"\d{6,}")
MASK_PATTERN = re.compile(r"<(?:ссылка|почта|ip|uuid|токен|телефон|ник|число)>")
WORD_PATTERN = re.compile(r"[a-zа-яё]+")
LAUGHTER_PATTERN = re.compile(
    r"(?i)(?:[аa]?[хx]+[аa]+[хx]*|[хx][аa]+[хx]+|[хx][еe]+[хx]+|кек+|лол+|\){2,})"
)


@dataclass(frozen=True)
class StyleMessage:
    chat_id: int
    message_id: int
    role: str
    text: str
    ts: datetime


@dataclass(frozen=True)
class Share:
    matched: int
    total: int

    @property
    def ratio(self) -> float:
        return self.matched / self.total if self.total else 0.0


@dataclass(frozen=True)
class LengthStats:
    count: int
    median: float | None
    p90: float | None


@dataclass(frozen=True)
class StyleStats:
    message_count: int
    owner_count: int
    them_count: int
    chat_count: int
    lengths: LengthStats
    lowercase_starts: Share
    no_terminal_dot: Share
    emoji: Share
    emoji_top: list[tuple[str, int]]
    laughter: Share
    laughter_top: list[tuple[str, int]]
    caps: Share
    owner_series_avg: float | None
    owner_series_max: int | None
    words: list[tuple[str, int]]
    short_replies: list[tuple[str, int]]
    samples: list[StyleMessage]
    pairs: list[tuple[str, str]]


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    if not 0 <= q <= 100:
        raise ValueError("q должен быть в диапазоне 0..100")
    ordered = sorted(values)
    index = max(0, math.ceil(q / 100 * len(ordered)) - 1)
    return float(ordered[index])


def mask_text(text: str) -> str:
    masked = URI_PATTERN.sub("<ссылка>", text)
    masked = EMAIL_PATTERN.sub("<почта>", masked)
    masked = UUID_PATTERN.sub("<uuid>", masked)
    masked = IPV4_PATTERN.sub("<ip>", masked)
    masked = PHONE_PATTERN.sub(_mask_phone, masked)
    masked = URL_PATTERN.sub("<ссылка>", masked)
    masked = TELEGRAM_LINK_PATTERN.sub("<ссылка>", masked)
    masked = MENTION_PATTERN.sub("<ник>", masked)
    masked = LONG_TOKEN_PATTERN.sub("<токен>", masked)
    return LONG_NUMBER_PATTERN.sub("<число>", masked)


def _mask_phone(match: re.Match[str]) -> str:
    value = match.group(0)
    digits = sum(char.isdigit() for char in value)
    has_separator = any(char in "+().-" or char.isspace() for char in value)
    return "<телефон>" if digits >= 7 and has_separator else value


def extract_emojis(text: str) -> list[str]:
    result: list[str] = []
    for char in text:
        codepoint = ord(char)
        if 0x1F3FB <= codepoint <= 0x1F3FF:
            continue
        if codepoint in (0x200D, 0xFE0F):
            continue
        if _is_emoji(codepoint):
            result.append(char)
    return result


def owner_series_lengths(messages: Sequence[StyleMessage]) -> list[int]:
    grouped: dict[int, list[StyleMessage]] = defaultdict(list)
    for message in messages:
        grouped[message.chat_id].append(message)

    result: list[int] = []
    for chat_id in sorted(grouped):
        ordered = sorted(grouped[chat_id], key=lambda item: (item.ts, item.message_id))
        current = 0
        for message in ordered:
            if message.role == "owner":
                current += 1
            elif current:
                result.append(current)
                current = 0
        if current:
            result.append(current)
    return result


def frequent_words(
    texts: Sequence[str],
    limit: int = 30,
    min_len: int = 2,
) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for text in texts:
        masked = MASK_PATTERN.sub(" ", mask_text(text)).casefold()
        for token in WORD_PATTERN.findall(masked):
            if len(token) >= min_len:
                counter[token] += 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def frequent_short_replies(
    texts: Sequence[str],
    max_len: int = 20,
    limit: int = 20,
) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for text in texts:
        normalized = mask_text(normalize_text(text))
        if 0 < len(normalized) <= max_len:
            counter[normalized] += 1
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]


def select_samples(
    messages: Sequence[StyleMessage],
    limit: int = 120,
    max_len: int = 160,
    seed: int = 42,
) -> list[StyleMessage]:
    candidates: list[StyleMessage] = []
    for message in _ordered(messages):
        if message.role != "owner":
            continue
        text = normalize_text(message.text)
        if not text or mask_text(text) != text:
            continue
        if len(text) <= max_len:
            candidates.append(
                StyleMessage(
                    chat_id=message.chat_id,
                    message_id=message.message_id,
                    role=message.role,
                    text=text,
                    ts=message.ts,
                )
            )

    rng = random.Random(seed)
    selected = rng.sample(candidates, min(limit, len(candidates)))
    return _ordered(selected)


def select_pairs(
    messages: Sequence[StyleMessage],
    limit: int = 25,
    seed: int = 42,
) -> list[tuple[str, str]]:
    grouped: dict[int, list[StyleMessage]] = defaultdict(list)
    for message in messages:
        grouped[message.chat_id].append(message)

    candidates: list[tuple[str, str]] = []
    for chat_id in sorted(grouped):
        ordered = sorted(grouped[chat_id], key=lambda item: (item.ts, item.message_id))
        for first, second in zip(ordered, ordered[1:]):
            if first.role != "them" or second.role != "owner":
                continue
            first_text = normalize_text(first.text)
            second_text = normalize_text(second.text)
            if not first_text or not second_text:
                continue
            if mask_text(first_text) != first_text or mask_text(second_text) != second_text:
                continue
            candidates.append((first_text, second_text))

    rng = random.Random(seed)
    indices = sorted(rng.sample(range(len(candidates)), min(limit, len(candidates))))
    return [candidates[index] for index in indices]


def build_style_stats(messages: Sequence[StyleMessage]) -> StyleStats:
    ordered = _ordered(messages)
    owner = [message for message in ordered if message.role == "owner"]
    owner_texts: list[str] = []
    for message in owner:
        text = normalize_text(message.text)
        if text:
            owner_texts.append(text)

    lengths = [len(text) for text in owner_texts]
    series = owner_series_lengths(ordered)
    emoji_counter = Counter(
        emoji for text in owner_texts for emoji in extract_emojis(text)
    )
    laughter_counter: Counter[str] = Counter()
    laughter_messages = 0
    for text in owner_texts:
        matches = [match.group(0).strip().casefold() for match in LAUGHTER_PATTERN.finditer(text)]
        if matches:
            laughter_messages += 1
            laughter_counter.update(matches)

    caps_matched = 0
    caps_total = 0
    for text in owner_texts:
        letters = [char for char in text if char.isalpha()]
        if len(letters) < 3:
            continue
        caps_total += 1
        if sum(char.isupper() for char in letters) / len(letters) >= 0.7:
            caps_matched += 1

    lowercase_matched = 0
    lowercase_total = 0
    for text in owner_texts:
        first_letter = next((char for char in text if char.isalpha()), None)
        if first_letter is None:
            continue
        lowercase_total += 1
        if not first_letter.isupper():
            lowercase_matched += 1

    no_dot_matched = sum(1 for text in owner_texts if text[-1] != ".")
    emoji_messages = sum(1 for text in owner_texts if extract_emojis(text))

    return StyleStats(
        message_count=len(ordered),
        owner_count=len(owner),
        them_count=sum(1 for message in ordered if message.role == "them"),
        chat_count=len({message.chat_id for message in ordered}),
        lengths=LengthStats(
            count=len(lengths),
            median=float(statistics.median(lengths)) if lengths else None,
            p90=percentile(lengths, 90),
        ),
        lowercase_starts=Share(lowercase_matched, lowercase_total),
        no_terminal_dot=Share(no_dot_matched, len(owner_texts)),
        emoji=Share(emoji_messages, len(owner_texts)),
        emoji_top=_top(emoji_counter, limit=10),
        laughter=Share(laughter_messages, len(owner_texts)),
        laughter_top=_top(laughter_counter, limit=10),
        caps=Share(caps_matched, caps_total),
        owner_series_avg=(sum(series) / len(series)) if series else None,
        owner_series_max=max(series) if series else None,
        words=frequent_words(owner_texts),
        short_replies=frequent_short_replies(owner_texts),
        samples=select_samples(ordered),
        pairs=select_pairs(ordered),
    )


def _ordered(messages: Sequence[StyleMessage]) -> list[StyleMessage]:
    return sorted(messages, key=lambda item: (item.chat_id, item.ts, item.message_id))


def _is_emoji(codepoint: int) -> bool:
    return (
        0x1F300 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
        or 0x1F1E6 <= codepoint <= 0x1F1FF
        or 0x2300 <= codepoint <= 0x23FF
        or 0x2B00 <= codepoint <= 0x2BFF
    )


def _top(counter: Counter[str], limit: int) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
