from __future__ import annotations

from datetime import datetime

from tgtwin.style.stats import Share, StyleStats


def render_report(stats: StyleStats, *, scope: str, generated_at: datetime) -> str:
    lines = [
        "Отчёт о стиле",
        f"Сформирован: {generated_at.isoformat()}",
        f"Область: {scope}",
        "",
        "Сводка",
        f"Сообщений: {stats.message_count}",
        f"Моих: {stats.owner_count}",
        f"Собеседников: {stats.them_count}",
        f"Чатов: {stats.chat_count}",
        "",
        "Длины моих сообщений",
        f"Медиана длины: {_number(stats.lengths.median)}",
        f"p90 длины: {_number(stats.lengths.p90)}",
        "",
        "Начала и окончания",
        f"Строчных начал: {_share(stats.lowercase_starts)}",
        f"Без точки в конце: {_share(stats.no_terminal_dot)}",
        f"Капс: {_share(stats.caps)}",
        "",
        "Эмодзи и смех",
        f"Сообщений с эмодзи: {_share(stats.emoji)}",
        f"Топ эмодзи: {_pairs(stats.emoji_top)}",
        f"Сообщений со смехом: {_share(stats.laughter)}",
        f"Топ смеха: {_pairs(stats.laughter_top)}",
        "",
        "Серии моих сообщений",
        f"Средняя серия: {_number(stats.owner_series_avg)}",
        f"Максимальная серия: {stats.owner_series_max if stats.owner_series_max is not None else '—'}",
        "",
        "Частые слова",
        _pairs(stats.words),
        "",
        "Частые короткие реплики",
        _pairs(stats.short_replies),
        "",
        "Примеры коротких сообщений",
    ]
    lines.extend(f"{index}. {sample.text}" for index, sample in enumerate(stats.samples, 1))
    if not stats.samples:
        lines.append("—")

    lines.extend(["", "Пары «собеседник → я»"])
    for index, (them_text, owner_text) in enumerate(stats.pairs, 1):
        lines.append(f"{index}. собеседник: {them_text}")
        lines.append(f"   я: {owner_text}")
    if not stats.pairs:
        lines.append("—")

    return "\n".join(lines) + "\n"


def _share(share: Share) -> str:
    if share.total == 0:
        return "— (0/0)"
    return f"{share.ratio * 100:.1f}% ({share.matched}/{share.total})"


def _number(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _pairs(values: list[tuple[str, int]]) -> str:
    if not values:
        return "—"
    return ", ".join(f"{value} ({count})" for value, count in values)
