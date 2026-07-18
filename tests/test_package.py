from pathlib import Path

from typer.testing import CliRunner

from schema_safe_bench import __version__
from schema_safe_bench.cli import app


def test_package_version() -> None:
    assert __version__ == "0.1.0"


def test_doctor_command() -> None:
    result = CliRunner().invoke(app, ["doctor"])
    assert result.exit_code == 0
    assert "installed" in result.stdout


def test_module_entrypoint_guard() -> None:
    assert app.info.help == "Schema-grounded text-to-SQL evaluation."


def test_readme_presents_results_without_budget_restrictions() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    lowered = readme.casefold()
    for prohibited in (
        "per-run cap",
        "project spend guard",
        "budget restriction",
        "blocked_by_budget",
        "$5 per run",
        "$95",
        "$100",
    ):
        assert prohibited not in lowered
    assert "| Method | Schema policy | Correct | Accuracy |" in readme
    assert all(f"[B{index}](results/b{index}-" in readme for index in range(8))


def test_cache_model_command_reports_pinned_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "schema_safe_bench.cli.cache_sentence_transformer",
        lambda _: type("Embedder", (), {"library_version": "fixture"})(),
    )
    monkeypatch.setattr(
        "schema_safe_bench.cli.cache_cross_encoder",
        lambda _: type("Reranker", (), {"library_version": "fixture"})(),
    )
    result = CliRunner().invoke(
        app,
        ["retrieval", "cache-model", "--config", "configs/runs/b3-openai-luna-smoke.yaml"],
    )

    assert result.exit_code == 0
    assert "BAAI/bge-small-en-v1.5@5c38ec7c" in result.stdout

    hybrid = CliRunner().invoke(
        app,
        ["retrieval", "cache-model", "--config", "configs/runs/b4-openai-luna-smoke.yaml"],
    )
    assert hybrid.exit_code == 0
    assert "BAAI/bge-small-en-v1.5@5c38ec7c" in hybrid.stdout

    reranked = CliRunner().invoke(
        app,
        ["retrieval", "cache-model", "--config", "configs/runs/b5-openai-luna-smoke.yaml"],
    )
    assert reranked.exit_code == 0
    assert "BAAI/bge-small-en-v1.5@5c38ec7c" in reranked.stdout
    assert "cross-encoder/ms-marco-MiniLM-L6-v2@c5ee24cb" in reranked.stdout
    assert "raw logits" in reranked.stdout
