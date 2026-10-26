from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tgtwin.style.report import render_report
from tgtwin.style.stats import StyleMessage, build_style_stats

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_report_masks_sensitive_values() -> None:
    messages = [
        StyleMessage(
            chat_id=1,
            message_id=1,
            role="them",
            text="Скинь https://secret.example @nick 123456789",
            ts=T0,
        ),
        StyleMessage(
            chat_id=1,
            message_id=2,
            role="owner",
            text="ок https://secret.example @nick 123456789",
            ts=T0 + timedelta(seconds=1),
        ),
    ]
    stats = build_style_stats(messages)

    report = render_report(
        stats,
        scope="chat 1",
        generated_at=datetime(2026, 10, 26, tzinfo=UTC),
    )

    assert "<ссылка>" in report
    assert "<ник>" in report
    assert "<число>" in report
    assert "secret.example" not in report
    assert "@nick" not in report
    assert "123456789" not in report
    assert "Медиана длины" in report
    assert "Частые слова" in report
    assert "Примеры" in report
    assert "Пары" in report
