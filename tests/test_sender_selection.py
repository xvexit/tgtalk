from __future__ import annotations

from tests.fakes import DummyBot, FakeMessageRepo
from tgtwin.adapters.telegram.sender import DryRunSender, TelegramBusinessSender
from tgtwin.app import choose_sender
from tgtwin.config import Settings


def test_send_enabled_true_selects_business_sender() -> None:
    s = Settings(SEND_ENABLED=True, DEEPSEEK_API_KEY="k", DATABASE_URL="x")
    sender = choose_sender(s, DummyBot(), FakeMessageRepo(), None)
    assert isinstance(sender, TelegramBusinessSender)


def test_send_enabled_false_selects_dry_run() -> None:
    s = Settings(SEND_ENABLED=False, DATABASE_URL="x")
    sender = choose_sender(s, DummyBot(), FakeMessageRepo(), None)
    assert isinstance(sender, DryRunSender)
