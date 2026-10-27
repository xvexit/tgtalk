from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from tgtwin.app import choose_llm
from tgtwin.config import Settings
from tgtwin.core.protocols import LLMProvider
from tgtwin.eval.judge import DeepSeekJudge, Judge
from tgtwin.eval.loader import load_messages
from tgtwin.eval.metrics import compute_metrics, load_profanity
from tgtwin.eval.models import CaseResult, EvalCase
from tgtwin.eval.runner import run_cases, run_judge
from tgtwin.eval.sampling import select_cases
from tgtwin.eval.storage import (
    compare_metrics,
    create_run_dir,
    format_show,
    resolve_run,
    write_run,
)
from tgtwin.llm.openai_compat import OpenAICompatProvider

PROFANITY_PATH = Path("config/profanity.txt")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m tgtwin.eval")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="запустить оценку")
    run.add_argument("--persona", required=True, type=Path)
    run.add_argument("--chats", required=True, help="ID чатов через запятую")
    run.add_argument("--cases", type=int, default=100)
    run.add_argument("--seed", type=int, default=1)
    run.add_argument("--no-judge", action="store_true")
    run.add_argument(
        "--empty-system",
        action="store_true",
        help="отбор по персоне, но генерация с пустым system-промптом",
    )

    show = subparsers.add_parser("show", help="показать кейсы прогона")
    show.add_argument("run")
    show.add_argument("--n", type=int, default=10)

    compare = subparsers.add_parser("compare", help="сравнить метрики прогонов")
    compare.add_argument("run1")
    compare.add_argument("run2")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return _run(args)
    if args.command == "show":
        print(format_show(resolve_run(args.run), args.n))
        return 0
    if args.command == "compare":
        run1 = resolve_run(args.run1)
        run2 = resolve_run(args.run2)
        print(f"run1: {run1}", file=sys.stderr)
        print(f"run2: {run2}", file=sys.stderr)
        print(
            json.dumps(compare_metrics(run1, run2), ensure_ascii=False, sort_keys=True)
        )
        return 0
    return 2


def _run(args: argparse.Namespace) -> int:
    if args.cases <= 0:
        raise SystemExit("--cases должен быть больше нуля")
    chat_ids = _parse_chats(args.chats)
    persona_text = args.persona.read_text(encoding="utf-8")
    settings = Settings()
    if not settings.DATABASE_URL:
        raise SystemExit("DATABASE_URL не задан")
    if not settings.DEEPSEEK_API_KEY:
        raise SystemExit("DEEPSEEK_API_KEY не задан")

    logging.info("eval_load chat_count=%s", len(chat_ids))
    messages_by_chat = asyncio.run(load_messages(chat_ids))
    cases, selection = select_cases(
        messages_by_chat,
        persona_text=persona_text,
        history_limit=settings.HISTORY_LIMIT,
        cases=args.cases,
        seed=args.seed,
    )
    if len(cases) < args.cases:
        logging.warning("eval_cases_short requested=%s selected=%s", args.cases, len(cases))
    if not cases:
        raise SystemExit("не удалось отобрать ни одного кейса")

    provider = choose_llm(settings)
    system = "" if args.empty_system else persona_text
    logging.info(
        "eval_generate cases=%s model=%s history_limit=%s",
        len(cases),
        settings.LLM_MODEL,
        settings.HISTORY_LIMIT,
    )
    results = _generate(cases, provider, system, settings)
    if not args.no_judge:
        judge_provider = OpenAICompatProvider(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.LLM_BASE_URL,
            model=settings.LLM_MODEL,
            timeout=settings.LLM_TIMEOUT,
            max_tokens=settings.LLM_MAX_TOKENS,
            thinking_enabled=settings.LLM_THINKING,
            temperature=0.0,
        )
        logging.info("eval_judge cases=%s", len(results))
        _judge(results, DeepSeekJudge(judge_provider), args.seed)

    profanity = load_profanity(PROFANITY_PATH)
    metrics = compute_metrics(
        results,
        judge_enabled=not args.no_judge,
        profanity_words=profanity,
    )
    metrics["selection"] = selection.as_dict()
    run_id, run_dir = create_run_dir()
    config = {
        "run_id": run_id,
        "created_at": datetime.now(UTC).isoformat(),
        "persona_path": str(args.persona),
        "persona_sha256": hashlib.sha256(persona_text.encode("utf-8")).hexdigest(),
        "persona_empty_system": args.empty_system,
        "chats": chat_ids,
        "cases_requested": args.cases,
        "cases_selected": len(cases),
        "seed": args.seed,
        "judge_enabled": not args.no_judge,
        "model": settings.LLM_MODEL,
        "thinking": settings.LLM_THINKING,
        "max_tokens": settings.LLM_MAX_TOKENS,
        "history_limit": settings.HISTORY_LIMIT,
    }
    write_run(run_dir, config, results, metrics)
    print(f"run: {run_dir}", file=sys.stderr)
    print(json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    return 0


def _generate(
    cases: Sequence[EvalCase],
    provider: LLMProvider,
    system: str,
    settings: Settings,
) -> list[CaseResult]:
    async def runner() -> list[CaseResult]:
        results: list[CaseResult] = []
        for index, case in enumerate(cases, 1):
            result = await run_cases(
                [case],
                provider,
                system=system,
                history_limit=settings.HISTORY_LIMIT,
            )
            results.extend(result)
            if index % 10 == 0 or index == len(cases):
                logging.info("eval_progress generated=%s total=%s", index, len(cases))
        return results

    return asyncio.run(runner())


def _judge(results: Sequence[CaseResult], judge: Judge, seed: int) -> None:
    asyncio.run(run_judge(results, judge, seed=seed))


def _parse_chats(value: str) -> list[int]:
    chat_ids = [int(part.strip()) for part in value.split(",") if part.strip()]
    if not chat_ids:
        raise SystemExit("--chats пуст")
    return chat_ids


if __name__ == "__main__":
    raise SystemExit(main())
