from __future__ import annotations

from tgtwin.core.pipeline import Pipeline
from tgtwin.core.protocols import LLMProvider
from tgtwin.steps.guard_owner import GuardOwnerStep
from tgtwin.steps.llm import LLMStep
from tgtwin.steps.postprocess import PostprocessStep
from tgtwin.steps.resolve_config import ResolveConfigStep


def build_pipeline(llm: LLMProvider) -> Pipeline:
    steps = [
        ResolveConfigStep(),
        GuardOwnerStep(),
        LLMStep(llm),
        PostprocessStep(),
    ]
    return Pipeline(steps)
