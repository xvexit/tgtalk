from __future__ import annotations

import pytest

from tests.fakes import FakeSender
from tgtwin.llm.fake import FakeLLMProvider


@pytest.fixture
def fake_sender() -> FakeSender:
    return FakeSender()


@pytest.fixture
def fake_llm() -> FakeLLMProvider:
    return FakeLLMProvider()
