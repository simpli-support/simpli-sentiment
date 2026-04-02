"""CLI interface."""

import typer
import uvicorn

from simpli_sentiment.settings import settings

app = typer.Typer(help="Simpli Sentiment CLI")


@app.command()
def serve(
    host: str = typer.Option(settings.app_host, help="Bind host"),
    port: int = typer.Option(settings.app_port, help="Bind port"),
    reload: bool = typer.Option(False, help="Enable auto-reload"),
    workers: int = typer.Option(settings.workers, help="Number of worker processes"),
    log_level: str = typer.Option(settings.app_log_level, help="Log level"),
) -> None:
    """Start the API server."""
    uvicorn.run(
        "simpli_sentiment.app:app",
        host=host,
        port=port,
        reload=reload,
        workers=workers,
        log_level=log_level.lower(),
    )


@app.command()
def version() -> None:
    """Show version."""
    from simpli_sentiment import __version__

    typer.echo(f"simpli-sentiment {__version__}")
