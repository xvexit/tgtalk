from __future__ import annotations

from datetime import UTC, datetime

from tgtwin.eval import storage
from tgtwin.eval.models import CaseResult, EvalCase, EvalMessage

BASE = datetime(2026, 1, 1, tzinfo=UTC)


def make_result() -> CaseResult:
    case = EvalCase(
        chat_id=1,
        trigger=EvalMessage(1, 2, "them", "вопрос", BASE),
        context=(EvalMessage(1, 1, "owner", "фон", BASE),),
        reference_messages=(EvalMessage(1, 3, "owner", "ответ", BASE),),
    )
    return CaseResult(
        case=case,
        bot="ответ",
        escalated=False,
        judge_choice="A",
        judge_a_is_reference=True,
        judge_correct=True,
    )


def test_write_read_and_show_run(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "RUNS_ROOT", tmp_path)
    run_id, run_dir = storage.create_run_dir(BASE)
    assert run_id == "20260101-000000"
    assert run_dir.is_dir()
    storage.write_run(
        run_dir,
        {"seed": 1},
        [make_result()],
        {"cases": 1, "valid_share": 1.0, "judge": {"accuracy": 1.0}},
    )
    assert storage.read_metrics(run_dir)["cases"] == 1
    rows = storage.read_cases(run_dir)
    assert rows[0]["trigger"]["text"] == "вопрос"
    assert rows[0]["judge"]["choice"] == "A"
    shown = storage.format_show(run_dir, 1)
    assert "reference: ответ" in shown
    assert "bot: ответ" in shown


def test_create_run_dir_avoids_collisions(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "RUNS_ROOT", tmp_path)
    first_id, first = storage.create_run_dir(BASE)
    second_id, second = storage.create_run_dir(BASE)
    assert first_id == "20260101-000000"
    assert second_id == "20260101-000000-1"
    assert first != second


def test_compare_metrics_reports_delta(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "RUNS_ROOT", tmp_path)
    _, first = storage.create_run_dir(BASE)
    _, second = storage.create_run_dir(BASE)
    storage.write_run(first, {}, [], {"cases": 1, "length": {"ks": 0.2}, "flag": True})
    storage.write_run(second, {}, [], {"cases": 3, "length": {"ks": 0.5}, "flag": False})
    compared = storage.compare_metrics(first, second)
    assert compared["cases"]["delta"] == 2
    assert compared["length.ks"]["run1"] == 0.2
    assert compared["length.ks"]["delta"] == 0.3
    assert compared["flag"]["run1"] is True


def test_resolve_run_accepts_id_or_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(storage, "RUNS_ROOT", tmp_path)
    run_id, run_dir = storage.create_run_dir(BASE)
    assert storage.resolve_run(run_id) == run_dir
    assert storage.resolve_run(str(run_dir)) == run_dir
