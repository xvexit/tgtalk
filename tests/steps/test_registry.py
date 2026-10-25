from __future__ import annotations

import pytest

from tgtwin.steps import registry


class FakeRepo:
    pass


class FakeProvider:
    pass


def test_new_steps_registered() -> None:
    registry.register_build_context(FakeRepo(), 30, "p")
    registry.register_llm(FakeProvider())
    registry.register_postprocess()
    for name in ("build_context", "llm", "postprocess"):
        step = registry.get(name)()
        assert callable(getattr(step, "handle", None))


def test_registry_reports_all_names() -> None:
    registry.register_postprocess()
    assert "postprocess" in registry.all_names()


def test_get_missing_raises() -> None:
    with pytest.raises(KeyError):
        registry.get("несуществующий")
