from __future__ import annotations

from collections.abc import Callable

from tgtwin.core.protocols import LLMProvider, MessageRepository, Step

_REGISTRY: dict[str, Callable[[], Step]] = {}


def register(name: str, factory: Callable[[], Step]) -> None:
    _REGISTRY[name] = factory


def get(name: str) -> Callable[[], Step]:
    return _REGISTRY[name]


def all_names() -> list[str]:
    return list(_REGISTRY.keys())


def register_build_context(repo: MessageRepository, history_limit: int, persona: str) -> None:
    from tgtwin.steps.build_context import BuildContextStep

    register("build_context", lambda: BuildContextStep(repo, persona, history_limit))


def register_llm(provider: LLMProvider) -> None:
    from tgtwin.steps.llm import LLMStep

    register("llm", lambda: LLMStep(provider))


def register_postprocess() -> None:
    from tgtwin.steps.postprocess import PostprocessStep

    register("postprocess", lambda: PostprocessStep())
