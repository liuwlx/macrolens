from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Job


async def enqueue_job(
    session: AsyncSession,
    *,
    job_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    priority: int = 0,
    max_attempts: int = 5,
) -> Job:
    """Create a durable job exactly once for an idempotency key.

    The insert is atomic under concurrent API/scheduler instances. The prior select-then-insert
    implementation could raise a unique-key error when two callers raced.
    """
    job, _created = await reserve_job(
        session,
        job_type=job_type,
        payload=payload,
        idempotency_key=idempotency_key,
        priority=priority,
        max_attempts=max_attempts,
    )
    await session.commit()
    return job


async def reserve_job(
    session: AsyncSession,
    *,
    job_type: str,
    payload: dict[str, Any],
    idempotency_key: str,
    priority: int = 0,
    max_attempts: int = 5,
) -> tuple[Job, bool]:
    """Atomically reserve an idempotency key without committing the caller's transaction."""
    job_id = uuid4()
    statement = (
        insert(Job)
        .values(
            id=job_id,
            job_type=job_type,
            payload=payload,
            idempotency_key=idempotency_key,
            priority=priority,
            max_attempts=max_attempts,
            run_after=datetime.now(UTC),
        )
        .on_conflict_do_nothing(index_elements=[Job.idempotency_key])
        .returning(Job.id)
    )
    created_id = await session.scalar(statement)
    resolved_id = created_id or await session.scalar(
        select(Job.id).where(Job.idempotency_key == idempotency_key)
    )
    if resolved_id is None:  # Defensive guard for an unexpected transaction/storage failure.
        raise RuntimeError("Failed to create or resolve idempotent job")
    job = await session.get(Job, resolved_id)
    if job is None:
        raise RuntimeError("Durable job disappeared after insertion")
    return job, created_id is not None
