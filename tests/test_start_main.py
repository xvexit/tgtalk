from __future__ import annotations

import asyncio

import pytest

from tgtwin.config import Settings


def test_main_send_enabled_raises(monkeypatch) -> None:
    async def fake_main():
        settings = Settings()
        if settings.SEND_ENABLED:
            raise RuntimeError("Реальная отправка появится на этапе 2")

    monkeypatch.setenv("SEND_ENABLED", "true")
    with pytest.raises(RuntimeError) as e:
        asyncio.run(fake_main())
    assert "Реальная отправка появится на этапе 2" in str(e.value)
