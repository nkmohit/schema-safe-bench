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


def test_cache_model_command_reports_pinned_model(monkeypatch) -> None:
    monkeypatch.setattr(
        "schema_safe_bench.cli.cache_sentence_transformer",
        lambda _: type("Embedder", (), {"library_version": "fixture"})(),
    )
    result = CliRunner().invoke(
        app,
        ["retrieval", "cache-model", "--config", "configs/runs/b3-openai-luna-smoke.yaml"],
    )

    assert result.exit_code == 0
    assert "BAAI/bge-small-en-v1.5@5c38ec7c" in result.stdout
