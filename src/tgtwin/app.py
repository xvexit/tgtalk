from __future__ import annotations

from tgtwin.config import Settings
from tgtwin.core.pipeline import Pipeline
from tgtwin.core.protocols import LLMProvider, MessageRepository
from tgtwin.steps.guard_owner import GuardOwnerStep
from tgtwin.steps.guard_takeover import GuardTakeoverStep
from tgtwin.steps.guard_text import GuardTextStep
from tgtwin.steps.llm import LLMStep
from tgtwin.steps.postprocess import PostprocessStep
from tgtwin.steps.record import RecordStep
from tgtwin.steps.resolve_config import ResolveConfigStep


def build_pipeline(repo: MessageRepository, llm: LLMProvider, settings: Settings) -> Pipeline:
    steps = [
        ResolveConfigStep(),
        RecordStep(repo),
        GuardOwnerStep(),
        GuardTakeoverStep(repo, default_hours=settings.takeover_hours),
        GuardTextStep(),
        LLMStep(llm),
        PostprocessStep(),
    ]
    return Pipeline(steps)
