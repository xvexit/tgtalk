from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tgtwin.style.stats import (
    StyleMessage,
    build_style_stats,
    extract_emojis,
    frequent_short_replies,
    frequent_words,
    mask_text,
    normalize_text,
    owner_series_lengths,
    percentile,
    select_pairs,
    select_samples,
)

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def _msg(
    message_id: int,
    role: str,
    text: str,
    chat_id: int = 1,
    offset: int = 0,
) -> StyleMessage:
    return StyleMessage(
        chat_id=chat_id,
        message_id=message_id,
        role=role,
        text=text,
        ts=T0 + timedelta(seconds=offset),
    )


def test_percentile_nearest_rank() -> None:
    assert percentile([], 90) is None
    assert percentile([1, 2, 3, 4], 50) == 2.0
    assert percentile([1, 2, 3, 4], 90) == 4.0


def test_normalize_text() -> None:
    assert normalize_text("  привет\n  мир  ") == "привет мир"
    assert normalize_text("   ") == ""


def test_masks_links_nicks_and_long_numbers() -> None:
    text = "смотри https://example.com @nick 123456789, номер +79990001122"

    masked = mask_text(text)

    assert "<ссылка>" in masked
    assert "<ник>" in masked
    assert "<телефон>" in masked
    assert "example.com" not in masked
    assert "@nick" not in masked
    assert "123456789" not in masked


def test_masks_each_sensitive_kind() -> None:
    assert mask_text("почта ivan.petrov+tag@example.co.uk") == "почта <почта>"
    assert (
        mask_text("vless://123e4567-e89b-12d3-a456-426614174000@example.com:443#node")
        == "<ссылка>"
    )
    assert mask_text("ftp://example.com/file") == "<ссылка>"
    assert mask_text("10.20.30.40") == "<ip>"
    assert mask_text("123e4567-e89b-12d3-a456-426614174000") == "<uuid>"
    assert mask_text("AKIAIOSFODNN7EXAMPLE") == "<токен>"
    assert mask_text("+7 (999) 123-45-67") == "<телефон>"
    assert mask_text("123456") == "<число>"
    assert mask_text("12345") == "12345"


def test_extract_emojis_skips_skin_tone_and_joiner() -> None:
    assert extract_emojis("привет 😊👍🏽❤️") == ["😊", "👍", "❤"]


def test_words_keep_short_replies_and_do_not_filter_stopwords() -> None:
    words = dict(
        frequent_words(
            ["ну да не ок", "я и ты", "https://x.ru/abc", "ну"],
            limit=10,
            min_len=2,
        )
    )

    assert words["ну"] == 2
    assert words["да"] == 1
    assert words["не"] == 1
    assert words["ок"] == 1
    assert words["ты"] == 1
    assert "я" not in words
    assert "и" not in words
    assert "ссылка" not in words


def test_frequent_short_replies() -> None:
    replies = dict(
        frequent_short_replies(["ок", "ок", "привет", "очень длинное сообщение"], max_len=6)
    )

    assert replies == {"ок": 2, "привет": 1}


def test_owner_series_lengths() -> None:
    messages = [
        _msg(1, "owner", "a", chat_id=1, offset=0),
        _msg(2, "owner", "b", chat_id=1, offset=1),
        _msg(3, "them", "c", chat_id=1, offset=2),
        _msg(4, "owner", "d", chat_id=1, offset=3),
        _msg(5, "owner", "e", chat_id=2, offset=0),
    ]

    assert owner_series_lengths(messages) == [2, 1, 1]


def test_select_samples_is_deterministic_and_skips_masked() -> None:
    messages = [
        _msg(i, "owner", f"текст {i}", offset=i)
        for i in range(200)
    ]
    messages.extend(
        _msg(1000 + i, "owner", f"текст {i} https://example.com/{i}", offset=1000 + i)
        for i in range(20)
    )

    first = select_samples(messages, limit=120, max_len=160, seed=42)
    second = select_samples(messages, limit=120, max_len=160, seed=42)

    assert len(first) == 120
    assert first == second
    assert all("<" not in m.text for m in first)
    assert all("https://" not in m.text for m in first)
    assert all(len(m.text) <= 160 for m in first)


def test_select_pairs_is_deterministic_and_skips_masked() -> None:
    messages = [
        _msg(1, "them", "как дела", offset=0),
        _msg(2, "owner", "норм", offset=1),
        _msg(3, "them", "Скинь https://example.com @nick", offset=2),
        _msg(4, "owner", "ок", offset=3),
        _msg(5, "them", "ещё", offset=4),
        _msg(6, "owner", "ахаха 123456789", offset=5),
    ]

    pairs = select_pairs(messages, limit=25, seed=42)

    assert pairs == [("как дела", "норм")]


def test_build_style_stats() -> None:
    messages = [
        _msg(1, "them", "привет", offset=0),
        _msg(2, "owner", "привет", offset=1),
        _msg(3, "owner", "Привет.", offset=2),
        _msg(4, "them", "как дела", offset=3),
        _msg(5, "owner", "123", offset=4),
        _msg(6, "owner", "ёлка!", offset=5),
        _msg(7, "them", "ну", offset=6),
        _msg(8, "owner", "ПРИВЕТ", offset=7),
        _msg(9, "owner", "ок 😊", offset=8),
        _msg(10, "owner", "ахаха", offset=9),
        _msg(11, "owner", ")))", offset=10),
        _msg(12, "owner", "лол", offset=11),
        _msg(13, "owner", "НУ ДА", offset=12),
    ]

    stats = build_style_stats(messages)

    assert stats.message_count == 13
    assert stats.owner_count == 10
    assert stats.them_count == 3
    assert stats.chat_count == 1
    assert stats.lowercase_starts.matched == 5
    assert stats.lowercase_starts.total == 8
    assert stats.no_terminal_dot.matched == 9
    assert stats.no_terminal_dot.total == 10
    assert stats.emoji.matched == 1
    assert stats.laughter.matched == 3
    assert stats.caps.matched == 2
    assert stats.caps.total == 7
    assert stats.owner_series_avg == 10 / 3
    assert stats.owner_series_max == 6
    assert ("ну", 1) in stats.words
    assert any(text == "ок 😊" for text, _ in stats.short_replies)
    assert stats.samples
    assert stats.pairs == [
        ("привет", "привет"),
        ("как дела", "123"),
        ("ну", "ПРИВЕТ"),
    ]
