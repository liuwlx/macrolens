from __future__ import annotations

import asyncio
import os
import socket
from contextlib import suppress
from typing import Awaitable, Callable

import typer

from macrolens_api.config import get_settings
from macrolens_api.logging import configure_logging, get_logger
from macrolens_worker.health import health_server

app = typer.Typer(no_args_is_help=True)
settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)


def _runtime_worker_id() -> str:
    base = settings.worker_id.strip() or "worker"
    return f"{base}:{socket.gethostname()}:{os.getpid()}"[:120]


async def _run_service(role: str, task_factory: Callable[[], Awaitable[None]]) -> None:
    health = asyncio.create_task(health_server(role))
    business = asyncio.create_task(task_factory())
    done, pending = await asyncio.wait({health, business}, return_when=asyncio.FIRST_EXCEPTION)
    for task in pending:
        task.cancel()
    for task in pending:
        with suppress(asyncio.CancelledError):
            await task
    for task in done:
        task.result()


@app.command("run")
def run() -> None:
    """Run the PostgreSQL-backed worker as a long-lived service."""
    from macrolens_worker.runner import worker_loop

    asyncio.run(_run_service("worker", lambda: worker_loop(_runtime_worker_id())))


@app.command("run-once")
def run_once() -> None:
    """Claim and execute at most one queued job, suitable for a one-shot job runner."""
    from macrolens_worker.runner import worker_once

    result = asyncio.run(worker_once(_runtime_worker_id()))
    raise typer.Exit(code=0 if result else 2)


@app.command("schedule")
def schedule() -> None:
    """Run the idempotent scheduler as a long-lived service."""
    from macrolens_worker.scheduler import scheduler_loop

    asyncio.run(_run_service("scheduler", scheduler_loop))


@app.command("schedule-once")
def schedule_once() -> None:
    """Enqueue the current scheduling tick and exit."""
    from macrolens_worker.scheduler import enqueue_schedule_tick

    result = asyncio.run(enqueue_schedule_tick())
    typer.echo(result)


@app.command("audit-data")
def audit_data(
    registry: str = typer.Option("database/seed/source_registry.json", help="Source registry JSON path"),
    output: str | None = typer.Option(None, help="Optional output JSON path"),
    structural: bool = typer.Option(False, help="Ignore secrets and audit mapping/adapter readiness only"),
    require_all: bool = typer.Option(
        False, help="Also fail for intentionally blocked mapping/license entries"
    ),
) -> None:
    """Audit whether every registered indicator is executable with current configuration."""
    import json
    from pathlib import Path

    from macrolens_worker.data_readiness import audit_source_registry

    report = audit_source_registry(Path(registry), check_credentials=not structural)
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    typer.echo(rendered)
    if not report["all_enabled_ready"]:
        raise typer.Exit(code=4)
    if require_all and not report["all_production_ready"]:
        raise typer.Exit(code=3)


@app.command("audit-live")
def audit_live(
    provider: list[str] | None = typer.Option(
        None, "--provider", help="Provider code to audit; repeat for multiple providers"
    ),
    mode: str = typer.Option(
        "incremental", help="incremental, backfill, or vintage_backfill"
    ),
    output: str | None = typer.Option(None, help="Optional output JSON path"),
) -> None:
    """Fetch enabled mappings without publishing and enforce completeness gates."""
    import json
    from pathlib import Path

    from macrolens_worker.live_audit import audit_live_data

    report = asyncio.run(audit_live_data(provider_codes=provider, mode=mode))
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if output:
        Path(output).write_text(rendered + "\n", encoding="utf-8")
    typer.echo(rendered)
    if not report["all_executed_passed"]:
        raise typer.Exit(code=5)


if __name__ == "__main__":
    app()
