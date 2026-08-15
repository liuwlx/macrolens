from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macrolens_api.db import SessionLocal
from macrolens_api.models import Dataset, Provider, SourceSeries
from macrolens_worker.providers.base import ProviderFetchResult
from macrolens_worker.tasks.ingestion_quality import validate_ingestion_completeness
from macrolens_worker.tasks.sync import ADAPTERS


def summarize_live_fetch(
    provider_code: str,
    mappings: list[tuple[SourceSeries, Dataset]],
    results: Iterable[ProviderFetchResult],
    *,
    mode: str,
) -> dict[str, Any]:
    result_list = list(results)
    observations = [item for result in result_list for item in result.observations]
    issues, metrics = validate_ingestion_completeness(mappings, observations, mode=mode)
    per_source: dict[str, dict[str, Any]] = {}
    by_source: dict[int, list[Any]] = {}
    for observation in observations:
        by_source.setdefault(observation.source_series_id, []).append(observation)
    for source, dataset in mappings:
        rows = by_source.get(source.id, [])
        periods = [row.period_start for row in rows]
        vintages = [row.vintage_at for row in rows]
        per_source[str(source.id)] = {
            "provider_series_id": source.provider_series_id,
            "dataset": dataset.code,
            "observation_count": len(rows),
            "non_null_count": sum(
                1 for row in rows if row.value is not None or row.value_text is not None
            ),
            "first_period": min(periods).isoformat() if periods else None,
            "latest_period": max(periods).isoformat() if periods else None,
            "first_vintage": min(vintages).isoformat() if vintages else None,
            "latest_vintage": max(vintages).isoformat() if vintages else None,
        }
    return {
        "provider": provider_code,
        "status": "passed" if not issues else "failed",
        "fetch_result_count": len(result_list),
        "raw_byte_count": sum(len(result.raw_bytes) for result in result_list),
        "metrics": metrics,
        "issues": [
            {
                "code": issue.code,
                "message": issue.message,
                "source_series_id": issue.source_series_id,
                "period_start": issue.period_start.isoformat() if issue.period_start else None,
            }
            for issue in issues
        ],
        "series": per_source,
    }


async def _provider_mappings(
    session: AsyncSession, provider: Provider
) -> list[tuple[SourceSeries, Dataset]]:
    return list(
        (
            await session.execute(
                select(SourceSeries, Dataset)
                .join(Dataset, Dataset.id == SourceSeries.dataset_id)
                .where(
                    Dataset.provider_id == provider.id,
                    Dataset.active.is_(True),
                    SourceSeries.mapping_status == "verified",
                    SourceSeries.is_primary.is_(True),
                )
                .order_by(Dataset.id, SourceSeries.id)
            )
        ).tuples().all()
    )


async def audit_live_data(
    *,
    provider_codes: list[str] | None = None,
    mode: str = "incremental",
) -> dict[str, Any]:
    if mode not in {"incremental", "backfill", "vintage_backfill"}:
        raise ValueError(f"Unsupported audit mode: {mode}")
    requested = set(provider_codes or [])
    provider_reports: list[dict[str, Any]] = []
    started_at = datetime.now(UTC)

    async with SessionLocal() as session:
        statement = select(Provider).where(Provider.active.is_(True)).order_by(Provider.code)
        if requested:
            statement = statement.where(Provider.code.in_(requested))
        providers = list((await session.scalars(statement)).all())
        found = {provider.code for provider in providers}
        missing = sorted(requested - found)
        for code in missing:
            provider_reports.append(
                {
                    "provider": code,
                    "status": "failed",
                    "issues": [
                        {"code": "provider_missing", "message": "Provider is not active or seeded."}
                    ],
                    "series": {},
                }
            )

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(120, connect=30),
            follow_redirects=True,
            headers={"User-Agent": "MacroLens/1.0.2 live-ingestion-audit"},
        ) as client:
            for provider in providers:
                adapter_type = ADAPTERS.get(provider.code)
                if adapter_type is None:
                    provider_reports.append(
                        {
                            "provider": provider.code,
                            "status": "failed",
                            "issues": [
                                {
                                    "code": "adapter_missing",
                                    "message": "No production adapter is registered.",
                                }
                            ],
                            "series": {},
                        }
                    )
                    continue
                mappings = await _provider_mappings(session, provider)
                if not mappings:
                    # Providers without enabled mappings are intentionally skipped rather than
                    # reported as healthy. This keeps legal/mapping blocks visible.
                    provider_reports.append(
                        {
                            "provider": provider.code,
                            "status": "skipped",
                            "issues": [
                                {
                                    "code": "no_verified_mappings",
                                    "message": "No verified primary mappings are enabled.",
                                }
                            ],
                            "series": {},
                        }
                    )
                    continue
                try:
                    results = await adapter_type(client).fetch(provider, mappings, mode=mode)
                    provider_reports.append(
                        summarize_live_fetch(provider.code, mappings, results, mode=mode)
                    )
                except Exception as exc:  # noqa: BLE001 - audit must report every provider
                    provider_reports.append(
                        {
                            "provider": provider.code,
                            "status": "failed",
                            "issues": [
                                {
                                    "code": "provider_fetch_failed",
                                    "message": f"{type(exc).__name__}: {exc}",
                                }
                            ],
                            "series": {},
                        }
                    )

    finished_at = datetime.now(UTC)
    executed = [report for report in provider_reports if report["status"] != "skipped"]
    verdict_reports = provider_reports if requested else executed
    return {
        "mode": mode,
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "provider_count": len(provider_reports),
        "executed_provider_count": len(executed),
        "passed_provider_count": sum(report["status"] == "passed" for report in executed),
        "failed_provider_count": sum(report["status"] == "failed" for report in executed),
        "skipped_provider_count": sum(report["status"] == "skipped" for report in provider_reports),
        "all_executed_passed": bool(verdict_reports) and all(
            report["status"] == "passed" for report in verdict_reports
        ),
        "providers": provider_reports,
    }
