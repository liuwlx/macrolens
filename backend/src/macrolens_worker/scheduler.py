from __future__ import annotations

import asyncio
from datetime import UTC, datetime


from macrolens_api.config import get_settings
from macrolens_api.logging import get_logger
from sqlalchemy import func, select

from macrolens_api.db import SessionLocal
from macrolens_api.models import Dataset, Provider, SourceSeries
from macrolens_api.services.jobs import enqueue_job

logger = get_logger(__name__)
settings = get_settings()

PROVIDER_CADENCE_HOURS = {
    "BEA_API": 1,
    "BLS_API_V2": 1,
    "CENSUS_EITS_API": 1,
    "DOL_OPEN_DATA_API": 1,
    "FRED_API": 6,
    "NYFED_MARKETS_API": 6,
    "US_TREASURY_XML": 6,
    "EIA_API_V2": 6,
}


async def enqueue_schedule_tick(now: datetime | None = None) -> dict[str, int]:
    current = now or datetime.now(UTC)
    queued = 0
    async with SessionLocal() as session:
        active_calendar_providers = set(
            (
                await session.scalars(
                    select(Provider.code).where(
                        Provider.code.in_({"BLS_API_V2", "FEDERAL_RESERVE"}),
                        Provider.active.is_(True),
                    )
                )
            ).all()
        )
        for provider, cadence in PROVIDER_CADENCE_HOURS.items():
            verified_count = await session.scalar(
                select(func.count(SourceSeries.id))
                .join(Dataset, Dataset.id == SourceSeries.dataset_id)
                .join(Provider, Provider.id == Dataset.provider_id)
                .where(
                    Provider.code == provider,
                    Provider.active.is_(True),
                    Dataset.active.is_(True),
                    SourceSeries.mapping_status == "verified",
                    SourceSeries.is_primary.is_(True),
                )
            )
            if not verified_count:
                # Unresolved or unlicensed mappings are intentionally not scheduled.
                continue
            slot = int(current.timestamp() // (cadence * 3600))
            try:
                await enqueue_job(
                    session,
                    job_type="sync_provider",
                    payload={"provider_code": provider, "mode": "incremental"},
                    idempotency_key=f"scheduled-sync:{provider}:{slot}",
                    priority=5,
                    max_attempts=5,
                )
                queued += 1
            except Exception:
                # Idempotency conflicts are expected when more than one scheduler instance runs.
                await session.rollback()
        day_key = current.strftime("%Y-%m-%d")
        if "FEDERAL_RESERVE" in active_calendar_providers:
            try:
                await enqueue_job(
                    session,
                    job_type="sync_fomc_calendar",
                    payload={},
                    idempotency_key=f"scheduled-fomc:{day_key}",
                    priority=6,
                    max_attempts=3,
                )
                queued += 1
            except Exception:
                await session.rollback()
        if "BLS_API_V2" in active_calendar_providers:
            try:
                await enqueue_job(
                    session,
                    job_type="sync_bls_release_calendar",
                    payload={},
                    idempotency_key=f"scheduled-bls-calendar:{day_key}",
                    priority=6,
                    max_attempts=3,
                )
                queued += 1
            except Exception:
                await session.rollback()
        alert_slot = int(current.timestamp() // 900)
        try:
            await enqueue_job(
                session,
                job_type="evaluate_alerts",
                payload={},
                idempotency_key=f"scheduled-alerts:{alert_slot}",
                priority=2,
                max_attempts=3,
            )
            queued += 1
        except Exception:
            await session.rollback()
    return {"queued": queued}


async def scheduler_loop() -> None:
    logger.info("scheduler_started")
    while True:
        try:
            result = await enqueue_schedule_tick()
            logger.info("scheduler_tick", **result)
        except Exception as exc:
            logger.exception("scheduler_tick_failed", error=str(exc))
        await asyncio.sleep(60)
