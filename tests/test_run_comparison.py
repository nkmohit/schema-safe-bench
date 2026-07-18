from pathlib import Path

import pytest

from schema_safe_bench.reporting import compare_paired_runs, load_traces, write_run_comparison

ROOT = Path(__file__).resolve().parents[1]
B0_TRACES = ROOT / "results" / "b0-openai-gpt-5-6-luna-smoke" / "trace.jsonl"


def test_identical_trace_sets_produce_zero_delta(tmp_path: Path) -> None:
    traces = load_traces(B0_TRACES)
    comparison = compare_paired_runs(traces, traces)

    assert comparison.baseline.correct == comparison.treatment.correct == 6
    assert comparison.deltas == {
        "correct": 0,
        "accuracy": 0.0,
        "abstained": 0,
        "invalid": 0,
        "execution_errors": 0,
        "schema_chars": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "estimated_cost_usd": 0.0,
    }
    assert comparison.context_truncated_tasks == 0
    assert not comparison.improved_task_ids
    assert not comparison.regressed_task_ids
    assert len(comparison.unchanged_task_ids) == 20

    output = tmp_path / "comparison.json"
    assert write_run_comparison(comparison, output) == output
    with pytest.raises(FileExistsError, match="already exists"):
        write_run_comparison(comparison, output)


def test_paired_comparison_rejects_different_task_sets() -> None:
    traces = load_traces(B0_TRACES)
    with pytest.raises(ValueError, match="identical task IDs"):
        compare_paired_runs(traces, traces[:-1])
