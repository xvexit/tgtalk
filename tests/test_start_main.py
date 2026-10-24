from __future__ import annotations

import pytest

from tgtwin import __main__
from tgtwin.config import Settings


def test_main_send_enabled_raises() -> None:
    s = Settings(BOT_TOKEN="x", DATABASE_URL="y", SEND_ENABLED=True)
    if s.SEND_ENABLED:
        raise RuntimeError("Реальная отправка появится на этапе 2")
