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
