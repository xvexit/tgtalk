from __future__ import annotations

from tgtwin.eval.filters import has_sensitive, leaks_persona


def test_has_sensitive_detects_links() -> None:
    assert has_sensitive("смотри https://example.com/page")
    assert has_sensitive("зайди на www.example.com")
    assert has_sensitive("пиши t.me/somebody")


def test_has_sensitive_detects_email() -> None:
    assert has_sensitive("пиши на test@example.com")


def test_has_sensitive_detects_long_number() -> None:
    assert has_sensitive("карта 1234567890")


def test_has_sensitive_detects_phone_with_separators() -> None:
    assert has_sensitive("звони +7 (999) 123-45-67")


def test_has_sensitive_detects_token() -> None:
    assert has_sensitive("ключ sk-abcdefghijklmnopqrstuvwxyz0123456789")


def test_has_sensitive_allows_short_number_and_plain_text() -> None:
    assert not has_sensitive("встретимся в 5")
    assert not has_sensitive("привет, как дела?")


def test_persona_leak_requires_exact_long_line() -> None:
    persona = "Привет! Меня зовут Алексей.\nЛюблю горы и кофе."
    assert leaks_persona("  Люблю горы   и кофе. ", persona)
    assert not leaks_persona("Люблю горы", persona)
    assert not leaks_persona("Люблю горы и кофе. И ещё море.", persona)


def test_persona_leak_ignores_short_lines() -> None:
    persona = "Привет\nОк"
    assert not leaks_persona("Привет", persona)
