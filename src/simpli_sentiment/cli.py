"""CLI interface."""

import typer
import uvicorn

app = typer.Typer(help="Simpli Sentiment CLI")


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind host"),
    port: int = typer.Option(8000, help="Bind port"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
) -> None:
    """Start the API server."""
    uvicorn.run("simpli_sentiment.app:app", host=host, port=port, reload=reload)


@app.command()
def version() -> None:
    """Show version."""
    from simpli_sentiment import __version__

    typer.echo(f"simpli-sentiment {__version__}")
