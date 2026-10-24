from __future__ import annotations

from aiogram.client.session.aiohttp import AiohttpSession

from tgtwin.config import Settings


def test_proxy_session_created() -> None:
    s = Settings(TELEGRAM_PROXY="http://127.0.0.1:12334")
    session = AiohttpSession(proxy=s.TELEGRAM_PROXY)
    assert session is not None


def test_no_proxy_empty() -> None:
    s = Settings(TELEGRAM_PROXY="")
    assert s.TELEGRAM_PROXY == ""
