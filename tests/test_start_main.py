from __future__ import annotations

from tgtwin.app import choose_llm, validate_startup
from tgtwin.config import Settings
from tgtwin.llm.fake import FakeLLMProvider
from tgtwin.llm.openai_compat import OpenAICompatProvider


def test_dry_run_without_key_uses_fake_and_warns(caplog) -> None:
    s = Settings(SEND_ENABLED=False, DEEPSEEK_API_KEY="", DATABASE_URL="x")
    validate_startup(s, "персона")
    llm = choose_llm(s)
    assert isinstance(llm, FakeLLMProvider)
    assert "LLM не настроена" in caplog.text


def test_dry_run_with_key_uses_real_provider(caplog) -> None:
    s = Settings(SEND_ENABLED=False, DEEPSEEK_API_KEY="k", DATABASE_URL="x")
    validate_startup(s, "персона")
    llm = choose_llm(s)
    assert isinstance(llm, OpenAICompatProvider)


def test_dry_run_without_persona_warns_and_starts(caplog) -> None:
    s = Settings(SEND_ENABLED=False, DEEPSEEK_API_KEY="", DATABASE_URL="x")
    validate_startup(s, "")
    assert "персона не задана" in caplog.text
