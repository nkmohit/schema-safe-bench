"""Command-line entry point."""

import typer

app = typer.Typer(no_args_is_help=True, help="Schema-grounded text-to-SQL evaluation.")


@app.callback()
def main() -> None:
    """Run SchemaSafeBench commands."""


@app.command()
def doctor() -> None:
    """Check that the package is installed."""
    typer.echo("SchemaSafeBench is installed.")


if __name__ == "__main__":
    app()
