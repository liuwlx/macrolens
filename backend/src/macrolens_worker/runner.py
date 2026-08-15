from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select

from macrolens_api.config import get_settings
from macrolens_api.db import SessionLocal
from macrolens_api.logging import get_logger
from macrolens_api.models import AIRun, Job
from macrolens_worker.tasks.ai import run_ai_analysis
from macrolens_worker.tasks.documents import (
    embed_document,
    fetch_document,
    parse_document,
    summarize_document,
)
from macrolens_worker.tasks.email import send_email_notification
from macrolens_worker.tasks.fomc import sync_fomc_calendar
from macrolens_worker.tasks.mappings import probe_mapping, replay_bls_raw
from macrolens_worker.tasks.notifications import evaluate_alerts
from macrolens_worker.tasks.release_calendar import sync_bls_release_calendar
from macrolens_worker.tasks.sync import sync_provider

logger = get_logger(__name__)
settings = get_settings()


async def claim_job(worker_id: str) -> Job | None:
    """Atomically claim a queued job or recover a stale running job.

    A crashed worker leaves the row in ``running``. The original implementation only queried
    ``queued`` jobs, so such work could remain stuck forever. A stale running row is reclaimable
    after the configured lock timeout and receives a new attempt.
    """
    async with SessionLocal() as session:
        now = datetime.now(UTC)
        stale_before = now - timedelta(seconds=settings.worker_job_lock_seconds)
        async with session.begin():
            job = await session.scalar(
                select(Job)
                .where(
                    Job.attempts < Job.max_attempts,
                    or_(
                        and_(Job.status == "queued", Job.run_after <= now),
                        and_(
                            Job.status == "running",
                            Job.locked_at.is_not(None),
                            Job.locked_at < stale_before,
                        ),
                    ),
                )
                .order_by(Job.priority.desc(), Job.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            if job is None:
                return None
            recovered = job.status == "running"
            job.status = "running"
            job.locked_by = worker_id[:120]
            job.locked_at = now
            job.heartbeat_at = now
            job.started_at = job.started_at or now
            job.finished_at = None
            job.attempts += 1
            if recovered:
                note = f"Recovered stale worker lock at {now.isoformat()}"
                job.last_error = f"{job.last_error}\n{note}".strip() if job.last_error else note
            await session.flush()
            session.expunge(job)
            return job


async def heartbeat_job(job_id: UUID, worker_id: str) -> bool:
    """Renew a running job lease. Returns false if ownership has changed."""
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None or job.status != "running" or job.locked_by != worker_id[:120]:
            return False
        now = datetime.now(UTC)
        job.locked_at = now
        job.heartbeat_at = now
        await session.commit()
        return True


async def finish_job(
    job_id: UUID,
    *,
    worker_id: str,
    result: dict[str, Any] | None = None,
) -> bool:
    """Finish a job only when the caller still owns its lease."""
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None or job.status != "running" or job.locked_by != worker_id[:120]:
            logger.warning("job_finish_lease_lost", job_id=str(job_id), worker_id=worker_id)
            return False
        job.status = "succeeded"
        job.result = result or {}
        job.finished_at = datetime.now(UTC)
        job.locked_by = None
        job.locked_at = None
        job.heartbeat_at = None
        await session.commit()
        return True


async def fail_job(job_id: UUID, error: Exception, *, worker_id: str) -> bool:
    """Record failure only when the caller still owns the job lease."""
    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if job is None or job.status != "running" or job.locked_by != worker_id[:120]:
            logger.warning("job_fail_lease_lost", job_id=str(job_id), worker_id=worker_id)
            return False
        job.last_error = f"{type(error).__name__}: {error}"
        job.locked_by = None
        job.locked_at = None
        job.heartbeat_at = None
        terminal = job.attempts >= job.max_attempts
        if terminal:
            job.status = "failed"
            job.finished_at = datetime.now(UTC)
        else:
            job.status = "queued"
            delay = min(3600, 15 * (2 ** max(0, job.attempts - 1)))
            job.run_after = datetime.now(UTC) + timedelta(seconds=delay)
        if job.job_type == "run_ai_analysis" and job.payload.get("ai_run_id"):
            ai_run = await session.get(AIRun, UUID(str(job.payload["ai_run_id"])))
            if ai_run is not None and ai_run.status != "cancelled":
                ai_run.status = "failed" if terminal else "queued"
                ai_run.error_message = job.last_error
                ai_run.completed_at = datetime.now(UTC) if terminal else None
        await session.commit()
        return True


async def _heartbeat_loop(job_id: UUID, worker_id: str, stop: asyncio.Event) -> None:
    interval = max(1.0, min(30.0, settings.worker_job_lock_seconds / 3))
    while not stop.is_set():
        try:
            await asyncio.wait_for(stop.wait(), timeout=interval)
        except TimeoutError:
            if not await heartbeat_job(job_id, worker_id):
                logger.warning("job_heartbeat_lease_lost", job_id=str(job_id), worker_id=worker_id)
                return


async def execute_job(job: Job) -> dict[str, Any]:
    async with SessionLocal() as session:
        payload = job.payload
        if job.job_type == "sync_provider":
            return await sync_provider(
                session,
                provider_code=str(payload["provider_code"]),
                mode=str(payload.get("mode", "incremental")),
                job_id=job.id,
                source_series_ids=(
                    [int(item) for item in payload["source_series_ids"]]
                    if payload.get("source_series_ids")
                    else None
                ),
            )
        if job.job_type == "mapping_probe":
            return await probe_mapping(
                session,
                source_series_id=int(payload["source_series_id"]),
            )
        if job.job_type == "replay_bls_raw":
            return await replay_bls_raw(
                session,
                raw_object_id=UUID(str(payload["raw_object_id"])),
                source_series_ids=[int(item) for item in payload["source_series_ids"]],
            )
        if job.job_type == "parse_document":
            return await parse_document(
                session,
                document_id=UUID(str(payload["document_id"])),
                raw_object_id=UUID(str(payload["raw_object_id"])),
            )
        if job.job_type == "fetch_document":
            return await fetch_document(session, **payload)
        if job.job_type == "embed_document":
            return await embed_document(
                session,
                document_version_id=UUID(str(payload["document_version_id"])),
            )
        if job.job_type == "run_ai_analysis":
            return await run_ai_analysis(session, ai_run_id=UUID(str(payload["ai_run_id"])))
        if job.job_type == "summarize_document":
            return await summarize_document(
                session, document_version_id=UUID(str(payload["document_version_id"]))
            )
        if job.job_type == "sync_fomc_calendar":
            return await sync_fomc_calendar(session)
        if job.job_type == "sync_bls_release_calendar":
            return await sync_bls_release_calendar(session)
        if job.job_type == "evaluate_alerts":
            workspace = UUID(str(payload["workspace_id"])) if payload.get("workspace_id") else None
            return await evaluate_alerts(session, workspace_id=workspace)
        if job.job_type == "send_email_notification":
            return await send_email_notification(
                session, notification_id=UUID(str(payload["notification_id"]))
            )
        raise RuntimeError(f"Unsupported job type: {job.job_type}")


async def _execute_with_heartbeat(job: Job, worker_id: str) -> None:
    stop = asyncio.Event()
    heartbeat = asyncio.create_task(_heartbeat_loop(job.id, worker_id, stop))
    try:
        logger.info("job_started", job_id=str(job.id), job_type=job.job_type, attempt=job.attempts)
        result = await execute_job(job)
        if await finish_job(job.id, worker_id=worker_id, result=result):
            logger.info("job_succeeded", job_id=str(job.id), result=result)
    except Exception as exc:
        logger.exception("job_failed", job_id=str(job.id), error=str(exc))
        await fail_job(job.id, exc, worker_id=worker_id)
        raise
    finally:
        stop.set()
        heartbeat.cancel()
        try:
            await heartbeat
        except asyncio.CancelledError:
            pass


async def worker_once(worker_id: str) -> bool:
    """Execute one available job and return whether a job was claimed."""
    job = await claim_job(worker_id)
    if job is None:
        return False
    await _execute_with_heartbeat(job, worker_id)
    return True


async def worker_loop(worker_id: str) -> None:
    semaphore = asyncio.Semaphore(settings.worker_concurrency)
    tasks: set[asyncio.Task[None]] = set()

    async def process(job: Job) -> None:
        async with semaphore:
            try:
                await _execute_with_heartbeat(job, worker_id)
            except Exception:
                # Failure is already persisted by _execute_with_heartbeat. Keep the service alive.
                return

    logger.info("worker_started", worker_id=worker_id, concurrency=settings.worker_concurrency)
    while True:
        tasks = {task for task in tasks if not task.done()}
        if len(tasks) >= settings.worker_concurrency:
            await asyncio.sleep(0.1)
            continue
        job = await claim_job(worker_id)
        if job is None:
            await asyncio.sleep(settings.worker_poll_seconds)
            continue
        task = asyncio.create_task(process(job))
        tasks.add(task)
