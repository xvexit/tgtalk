from __future__ import annotations

from tgtwin.core.pipeline import Pipeline
from tgtwin.core.protocols import LLMProvider
from tgtwin.steps.guard_owner import GuardOwnerStep
from tgtwin.steps.guard_takeover import GuardTakeoverStep
from tgtwin.steps.guard_text import GuardTextStep
from tgtwin.steps.llm import LLMStep
from tgtwin.steps.postprocess import PostprocessStep
from tgtwin.steps.record import RecordStep
from tgtwin.steps.resolve_config import ResolveConfigStep


def build_pipeline(llm: LLMProvider) -> Pipeline:
    steps = [
        ResolveConfigStep(),
        RecordStep(repo=_noop_repo()),  # type: ignore
        GuardOwnerStep(),
        GuardTakeoverStep(repo=_noop_repo()),  # type: ignore
        GuardTextStep(),
        LLMStep(llm),
        PostprocessStep(),
    ]
    return Pipeline(steps)


class _noop_repo:
    async def add(self, msg):  # type: ignore
        return None

    async def exists(self, chat_id: int, message_id: int):  # type: ignore
        return False

    async def last(self, chat_id: int, n: int):  # type: ignore
        return []

    async def last_owner_ts(self, chat_id: int):  # type: ignore
        return None
