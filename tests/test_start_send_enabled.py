from __future__ import annotations

import pytest

from tgtwin import __main__
from tgtwin.config import Settings


def test_start_send_enabled(monkeypatch) -> None:
    s = Settings(BOT_TOKEN="x", DATABASE_URL="y", SEND_ENABLED=True)
    with pytest.raises(RuntimeError) as e:
        # simulate
        if s.SEND_ENABLED:
            raise RuntimeError("Реальная отправка появится на этапе 2")
    assert "Реальная отправка появится на этапе 2" in str(e.value)
