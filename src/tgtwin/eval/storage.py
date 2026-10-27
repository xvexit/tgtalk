from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from tgtwin.eval.models import CaseResult, EvalMessage

RUNS_ROOT = Path("data/eval")


def create_run_dir(now: datetime | None = None) -> tuple[str, Path]:
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    base = RUNS_ROOT / timestamp
    candidate = base
    suffix = 1
    while candidate.exists():
        candidate = base.with_name(f"{timestamp}-{suffix}")
        suffix += 1
    candidate.mkdir(parents=True)
    return candidate.name, candidate


def write_run(
    run_dir: Path,
    config: dict[str, Any],
    results: list[CaseResult],
    metrics: dict[str, Any],
) -> None:
    _write_json(run_dir / "run.json", config)
    _write_json(run_dir / "metrics.json", metrics)
    with (run_dir / "cases.jsonl").open("w", encoding="utf-8") as file:
        for result in results:
            file.write(json.dumps(_result_to_dict(result), ensure_ascii=False) + "\n")


def resolve_run(value: str) -> Path:
    path = Path(value)
    if path.is_dir():
        return path
    candidate = RUNS_ROOT / value
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(f"прогон не найден: {value}")


def read_metrics(run_dir: Path) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads((run_dir / "metrics.json").read_text(encoding="utf-8")),
    )


def read_cases(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "cases.jsonl"
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def format_show(run_dir: Path, n: int) -> str:
    rows = read_cases(run_dir)
    lines = [f"run: {run_dir}", f"cases: {len(rows)}"]
    for index, row in enumerate(rows[: max(0, n)], 1):
        lines.append("")
        lines.append(
            f"case {index} chat={row['chat_id']} trigger_id={row['trigger']['message_id']} "
            f"ts={row['trigger']['ts']}"
        )
        for message in row["context"]:
            lines.append(f"  {message['role']}: {message['text']}")
        lines.append(f"  them: {row['trigger']['text']}")
        lines.append(f"  reference: {row['reference']}")
        lines.append(f"  bot: {row['bot']}")
        lines.append(f"  escalated: {row['escalated']}")
        judge = row.get("judge")
        if judge is not None:
            lines.append(
                f"  judge: choice={judge['choice']} correct={judge['correct']}"
            )
    return "\n".join(lines)


def compare_metrics(run1: Path, run2: Path) -> dict[str, Any]:
    left = _flatten(read_metrics(run1))
    right = _flatten(read_metrics(run2))
    compared: dict[str, Any] = {}
    for key in sorted(set(left) | set(right)):
        first = left.get(key)
        second = right.get(key)
        delta = None
        if isinstance(first, int | float) and isinstance(second, int | float):
            delta = second - first
        compared[key] = {"run1": first, "run2": second, "delta": delta}
    return compared


def _result_to_dict(result: CaseResult) -> dict[str, Any]:
    judge = None
    if result.judge_choice is not None:
        judge = {
            "choice": result.judge_choice,
            "a_is_reference": result.judge_a_is_reference,
            "correct": result.judge_correct,
        }
    return {
        "chat_id": result.case.chat_id,
        "trigger": _message_to_dict(result.case.trigger),
        "context": [_message_to_dict(message) for message in result.case.context],
        "reference": result.case.reference,
        "reference_count": result.case.reference_count,
        "bot": result.bot,
        "escalated": result.escalated,
        "error": result.error,
        "judge": judge,
    }


def _message_to_dict(message: EvalMessage) -> dict[str, Any]:
    return {
        "message_id": message.message_id,
        "role": message.role,
        "text": message.text,
        "ts": message.ts.isoformat(),
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            nested = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(item, nested))
    elif isinstance(value, list):
        return result
    else:
        result[prefix] = value
    return result
