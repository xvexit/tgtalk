from __future__ import annotations

import logging
from typing import Any

from tgtwin.config import Settings
from tgtwin.core.models import Mode
from tgtwin.core.pipeline import Pipeline
from tgtwin.core.protocols import LLMProvider, MessageRepository, ReplyLogRepository, Sender
from tgtwin.llm.fake import FakeLLMProvider
from tgtwin.llm.openai_compat import OpenAICompatProvider
from tgtwin.steps import registry as step_registry
from tgtwin.steps.guard_owner import GuardOwnerStep
from tgtwin.steps.guard_takeover import GuardTakeoverStep
from tgtwin.steps.guard_text import GuardTextStep
from tgtwin.steps.record import RecordStep
from tgtwin.steps.resolve_config import ResolveConfigStep

logger = logging.getLogger(__name__)


def validate_startup(settings: Settings, persona_text: str) -> None:
    if settings.SEND_ENABLED and not settings.DEEPSEEK_API_KEY:
        raise RuntimeError("SEND_ENABLED=true, но DEEPSEEK_API_KEY не задан")
    if settings.SEND_ENABLED and not persona_text.strip():
        raise RuntimeError("SEND_ENABLED=true, но персона не задана или пуста")
    if settings.SEND_ENABLED:
        logger.warning("реальная отправка включена")
    else:
        if not settings.DEEPSEEK_API_KEY:
            logger.warning("LLM не настроена, ответы фиктивные")
        if not persona_text.strip():
            logger.warning("персона не задана, ответы без system-промпта")


def choose_llm(settings: Settings) -> LLMProvider:
    if settings.DEEPSEEK_API_KEY:
        return OpenAICompatProvider(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            timeout=settings.LLM_TIMEOUT,
            max_tokens=settings.LLM_MAX_TOKENS,
            thinking_enabled=settings.LLM_THINKING,
        )
    return FakeLLMProvider()


def choose_sender(settings: Settings, bot: Any, repo: MessageRepository, resolver: Any) -> Sender:
    from tgtwin.adapters.telegram.sender import DryRunSender, TelegramBusinessSender

    if settings.SEND_ENABLED:
        return TelegramBusinessSender(bot, repo, resolver)
    return DryRunSender(bot, resolver)


def build_pipeline(
    repo: MessageRepository,
    llm: LLMProvider,
    settings: Settings,
    log_repo: ReplyLogRepository,
    persona_text: str = "",
) -> Pipeline:
    step_registry.register_guard_rate_limit(log_repo, settings.MAX_REPLIES_PER_HOUR)
    step_registry.register_build_context(repo, settings.HISTORY_LIMIT, persona_text)
    step_registry.register_llm(llm)
    step_registry.register_postprocess()
    step_registry.register_log_reply(log_repo, settings.LLM_MODEL)
    default_mode = Mode.AUTO if settings.SEND_ENABLED else Mode.DRY_RUN
    steps = [
        ResolveConfigStep(default_mode=default_mode),
        RecordStep(repo),
        GuardOwnerStep(),
        GuardTakeoverStep(repo, default_hours=settings.takeover_hours),
        GuardTextStep(),
        step_registry.get("guard_rate_limit")(),
        step_registry.get("build_context")(),
        step_registry.get("llm")(),
        step_registry.get("postprocess")(),
        step_registry.get("log_reply")(),
    ]
    return Pipeline(steps)
