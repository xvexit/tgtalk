from __future__ import annotations

from collections.abc import Callable

from tgtwin.core.protocols import Step

_REGISTRY: dict[str, Callable[[], Step]] = {}


def register(name: str, factory: Callable[[], Step]) -> None:
    _REGISTRY[name] = factory


def get(name: str) -> Callable[[], Step]:
    return _REGISTRY[name]


def all_names() -> list[str]:
    return list(_REGISTRY.keys())
