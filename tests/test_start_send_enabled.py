from __future__ import annotations

import pytest

from tgtwin.app import validate_startup
from tgtwin.config import Settings


def test_send_enabled_without_key_raises() -> None:
    s = Settings(SEND_ENABLED=True, DEEPSEEK_API_KEY="", DATABASE_URL="x")
    with pytest.raises(RuntimeError) as e:
        validate_startup(s, "персона")
    assert "DEEPSEEK_API_KEY" in str(e.value)


def test_send_enabled_without_persona_raises() -> None:
    s = Settings(SEND_ENABLED=True, DEEPSEEK_API_KEY="k", DATABASE_URL="x")
    with pytest.raises(RuntimeError) as e:
        validate_startup(s, "")
    assert "персона" in str(e.value)


def test_send_enabled_with_empty_persona_raises() -> None:
    s = Settings(SEND_ENABLED=True, DEEPSEEK_API_KEY="k", DATABASE_URL="x")
    with pytest.raises(RuntimeError):
        validate_startup(s, "   \n ")


def test_send_enabled_ok_warns(caplog) -> None:
    s = Settings(SEND_ENABLED=True, DEEPSEEK_API_KEY="k", DATABASE_URL="x")
    validate_startup(s, "персона")
    assert "реальная отправка включена" in caplog.text
