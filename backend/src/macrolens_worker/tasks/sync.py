from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Any, Literal, cast
from uuid import UUID

import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from macrolens_api.models import (
    Dataset,
    IngestionRun,
    ObservationLatest,
    ObservationVintage,
    Provider,
    PublicationBatch,
    QualityResult,
    RawObject,
    Series,
    SourceSeries,
)
from macrolens_api.services.storage import ObjectStorage
from macrolens_worker.providers import (
    BEAAdapter,
    BLSAdapter,
    CensusEITSAdapter,
    DOLOpenDataAdapter,
    EIAAdapter,
    FederalReserveBoardAdapter,
    FREDAdapter,
    NYFedAdapter,
    TradingViewAdapter,
    TreasuryAdapter,
)
from macrolens_worker.providers.base import (
    NormalizedObservation,
    ProviderAdapter,
    ProviderFetchResult,
)
from macrolens_worker.tasks.ingestion_quality import (
    CompletenessIssue,
    validate_ingestion_completeness,
)

ADAPTERS: dict[str, type[ProviderAdapter]] = {
    FREDAdapter.code: FREDAdapter,
    BLSAdapter.code: BLSAdapter,
    CensusEITSAdapter.code: CensusEITSAdapter,
    DOLOpenDataAdapter.code: DOLOpenDataAdapter,
    BEAAdapter.code: BEAAdapter,
    TreasuryAdapter.code: TreasuryAdapter,
    NYFedAdapter.code: NYFedAdapter,
    EIAAdapter.code: EIAAdapter,
    FederalReserveBoardAdapter.code: FederalReserveBoardAdapter,
    TradingViewAdapter.code: TradingViewAdapter,
}

TRADINGVIEW_NONCONTIGUOUS_BACKFILL_FREQUENCIES = frozenset(
    {"weekly", "monthly", "quarterly", "annual"}
)
TRADINGVIEW_BACKFILL_LOCK_NAMESPACE = int.from_bytes(b"MLTV", "big")


async def _raw_object(
    session: AsyncSession,
    storage: ObjectStorage,
    *,
    provider: Provider,
    dataset: Dataset | None,
    result: ProviderFetchResult,
) -> RawObject:
    now = result.captured_at or datetime.now(UTC)
    suffix = (
        "json"
        if "json" in result.content_type
        else "xml"
        if "xml" in result.content_type
        else "bin"
    )
    digest = hashlib.sha256(result.raw_bytes).hexdigest()
    existing = await session.scalar(
        select(RawObject).where(RawObject.provider_id == provider.id, RawObject.sha256 == digest)
    )
    if existing:
        return existing
    request_digest = hashlib.sha256(result.request_url.encode("utf-8")).hexdigest()[:12]
    key = PurePosixPath(
        "raw",
        provider.code.lower(),
        f"{now:%Y}",
        f"{now:%m}",
        f"{now:%d}",
        f"{now:%Y%m%dT%H%M%S%fZ}-{request_digest}-{digest[:16]}.{suffix}",
    ).as_posix()
    stored = await storage.put_bytes(key, result.raw_bytes, result.content_type)
    raw = RawObject(
        provider_id=provider.id,
        dataset_id=dataset.id if dataset else None,
        object_uri=stored.uri,
        content_type=stored.content_type,
        byte_size=stored.byte_size,
        sha256=stored.sha256,
        request_url=result.request_url,
        request_parameters=result.request_parameters,
        http_status=200,
        source_last_modified=result.source_last_modified,
        fetched_at=now,
    )
    session.add(raw)
    await session.flush()
    return raw


@dataclass(frozen=True, slots=True)
class ObservationMergeDecision:
    outcome: Literal["inserted", "revised", "unchanged"]
    update_latest: bool
    latest_status: str
    vintage_status: str


def decide_observation_merge(
    observation: NormalizedObservation,
    latest: ObservationLatest | None,
) -> ObservationMergeDecision:
    """Classify an incoming immutable vintage before any database writes.

    Every distinct vintage must be retained even when it is older than the serving
    row or carries the same value. Only the newest vintage may update
    ``observation_latest``.
    """
    if latest is None:
        return ObservationMergeDecision(
            outcome="inserted",
            update_latest=True,
            latest_status=observation.status,
            vintage_status=observation.status,
        )

    same_value = latest.value == observation.value and latest.value_text == observation.value_text
    if observation.vintage_at < latest.vintage_at:
        return ObservationMergeDecision(
            outcome="unchanged",
            update_latest=False,
            latest_status=latest.observation_status,
            vintage_status=observation.status,
        )
    if observation.vintage_at == latest.vintage_at:
        if not same_value:
            raise ValueError(
                "Incoming observation conflicts with observation_latest for the same vintage"
            )
        return ObservationMergeDecision(
            outcome="unchanged",
            update_latest=False,
            latest_status=latest.observation_status,
            vintage_status=observation.status,
        )
    if same_value:
        return ObservationMergeDecision(
            outcome="unchanged",
            update_latest=True,
            latest_status=latest.observation_status,
            vintage_status=observation.status,
        )
    return ObservationMergeDecision(
        outcome="revised",
        update_latest=True,
        latest_status="revised",
        vintage_status="revised",
    )


def _same_vintage_payload(existing: ObservationVintage, observation: NormalizedObservation) -> bool:
    return (
        existing.period_end == observation.period_end
        and existing.value == observation.value
        and existing.value_text == observation.value_text
        and existing.published_at == observation.published_at
        and existing.source_updated_at == observation.source_updated_at
    )


def _same_raw_payload(
    existing: ObservationVintage, observation: NormalizedObservation
) -> bool:
    return (
        existing.period_end == observation.period_end
        and existing.value == observation.value
        and existing.value_text == observation.value_text
        and existing.observation_status == observation.status
        and existing.published_at == observation.published_at
        and existing.quality_flags == observation.quality_flags
    )


async def _merge_observation(
    session: AsyncSession,
    observation: NormalizedObservation,
    *,
    run_id: UUID,
    raw_object_id: UUID | None,
    publication_batch_id: UUID,
) -> str:
    replayed_vintage = await session.scalar(
        select(ObservationVintage).where(
            ObservationVintage.source_series_id == observation.source_series_id,
            ObservationVintage.period_start == observation.period_start,
            ObservationVintage.raw_object_id == raw_object_id,
            ObservationVintage.vintage_at == observation.vintage_at,
        )
    )
    if replayed_vintage is not None:
        if not _same_raw_payload(replayed_vintage, observation):
            raise ValueError(
                "The same raw object produced a different immutable observation payload"
            )
        return "unchanged"

    exact_vintage = await session.scalar(
        select(ObservationVintage)
        .where(
            ObservationVintage.source_series_id == observation.source_series_id,
            ObservationVintage.period_start == observation.period_start,
            ObservationVintage.vintage_at == observation.vintage_at,
        )
        .execution_options(populate_existing=True)
    )
    if exact_vintage is not None and not _same_vintage_payload(exact_vintage, observation):
        raise ValueError(
            "Provider attempted to rewrite an immutable observation vintage with different data"
        )

    latest = await session.scalar(
        select(ObservationLatest)
        .where(
            ObservationLatest.source_series_id == observation.source_series_id,
            ObservationLatest.period_start == observation.period_start,
        )
        .execution_options(populate_existing=True)
    )
    decision = decide_observation_merge(observation, latest)

    # Preserve every unique point-in-time vintage, including older and unchanged
    # releases. This is required for revision analysis and point-in-time backtests.
    if exact_vintage is None:
        session.add(
            ObservationVintage(
                source_series_id=observation.source_series_id,
                period_start=observation.period_start,
                period_end=observation.period_end,
                value=observation.value,
                value_text=observation.value_text,
                observation_status=decision.vintage_status,
                published_at=observation.published_at,
                vintage_at=observation.vintage_at,
                source_updated_at=observation.source_updated_at,
                run_id=run_id,
                publication_batch_id=publication_batch_id,
                raw_object_id=raw_object_id,
                quality_flags=observation.quality_flags,
            )
        )

    if decision.update_latest:
        statement = insert(ObservationLatest).values(
            source_series_id=observation.source_series_id,
            period_start=observation.period_start,
            period_end=observation.period_end,
            value=observation.value,
            value_text=observation.value_text,
            observation_status=decision.latest_status,
            published_at=observation.published_at,
            vintage_at=observation.vintage_at,
            run_id=run_id,
            publication_batch_id=publication_batch_id,
            updated_at=datetime.now(UTC),
        )
        statement = statement.on_conflict_do_update(
            index_elements=[ObservationLatest.source_series_id, ObservationLatest.period_start],
            set_={
                "period_end": statement.excluded.period_end,
                "value": statement.excluded.value,
                "value_text": statement.excluded.value_text,
                "observation_status": statement.excluded.observation_status,
                "published_at": statement.excluded.published_at,
                "vintage_at": statement.excluded.vintage_at,
                "run_id": statement.excluded.run_id,
                "publication_batch_id": statement.excluded.publication_batch_id,
                "updated_at": statement.excluded.updated_at,
            },
            where=statement.excluded.vintage_at > ObservationLatest.vintage_at,
        )
        await session.execute(statement)
    return decision.outcome


async def _quarantine(
    session: AsyncSession,
    *,
    run: IngestionRun,
    code: str,
    message: str,
) -> None:
    session.add(
        QualityResult(
            run_id=run.id,
            rule_code=code,
            severity="blocking",
            passed=False,
            message=message,
        )
    )
    run.status = "quarantined"
    run.error_code = code
    run.error_message = message
    run.finished_at = datetime.now(UTC)
    await session.commit()


def ingestion_issue_severity(
    provider_code: str,
    issue: CompletenessIssue,
    missing_source_ids: set[int],
    *,
    mode: str,
) -> Literal["warning", "blocking"]:
    if provider_code != TradingViewAdapter.code:
        return "blocking"
    if issue.code == "stale_latest_period":
        return "warning"
    if (
        mode == "backfill"
        and issue.code == "history_gap"
        and issue.source_frequency in TRADINGVIEW_NONCONTIGUOUS_BACKFILL_FREQUENCIES
    ):
        return "warning"
    if issue.source_series_id in missing_source_ids and issue.code in {
        "mapped_series_missing",
        "mapped_series_all_null",
        "missing_observation_value",
        "minimum_history",
    }:
        return "warning"
    return "blocking"


async def sync_provider(
    session: AsyncSession,
    *,
    provider_code: str,
    mode: str = "incremental",
    job_id: UUID,
    source_series_ids: list[int] | None = None,
) -> dict[str, Any]:
    provider = await session.scalar(
        select(Provider).where(Provider.code == provider_code, Provider.active.is_(True))
    )
    if provider is None:
        raise RuntimeError(f"Unknown or inactive provider: {provider_code}")
    adapter_type = ADAPTERS.get(provider_code)
    if adapter_type is None:
        raise RuntimeError(f"No production adapter registered for {provider_code}")
    if provider_code == TradingViewAdapter.code and mode == "backfill":
        lock_key = (TRADINGVIEW_BACKFILL_LOCK_NAMESPACE << 32) | provider.id
        await session.execute(select(func.pg_advisory_xact_lock(lock_key)))
    mapping_statement = (
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
    requested_ids = set(source_series_ids or [])
    if source_series_ids is not None:
        if not requested_ids or len(requested_ids) != len(source_series_ids):
            raise RuntimeError("source_series_ids must contain unique positive IDs")
        mapping_statement = mapping_statement.where(SourceSeries.id.in_(requested_ids))
    mapping_rows = (await session.execute(mapping_statement)).tuples().all()
    if not mapping_rows:
        raise RuntimeError(f"Provider {provider_code} has no verified source mappings")
    mapping_pairs = [(row[0], row[1]) for row in mapping_rows]
    resolved_ids = {source.id for source, _dataset in mapping_pairs}
    if source_series_ids is not None and resolved_ids != requested_ids:
        raise RuntimeError(
            "Scoped sync contains an unknown, inactive, non-primary, or unverified mapping"
        )

    scope_payload = ",".join(str(item) for item in sorted(resolved_ids))
    scope_key = hashlib.sha256(scope_payload.encode("ascii")).hexdigest()

    run = IngestionRun(
        provider_id=provider.id,
        run_type="backfill" if mode in {"backfill", "vintage_backfill"} else "incremental",
        business_key=f"{provider_code}:{mode}:scope-sha256:{scope_key}:{job_id}",
        scheduled_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        status="running",
    )
    session.add(run)
    await session.flush()

    storage = ObjectStorage()
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(60, connect=20),
        follow_redirects=True,
        headers={"User-Agent": "MacroLens/1.0 research-data-platform"},
    ) as client:
        adapter = adapter_type(client)
        results = await adapter.fetch(provider, mapping_pairs, mode=mode)

    if not results:
        await _quarantine(
            session,
            run=run,
            code="non_empty_provider_result",
            message="Provider returned no fetch results.",
        )
        raise RuntimeError(f"Provider {provider_code} returned no data")

    staged_by_key: dict[
        tuple[int, object, object], tuple[NormalizedObservation, UUID | None]
    ] = {}
    for result in results:
        raw_id: UUID | None = None
        if result.persist_raw:
            raw = await _raw_object(
                session,
                storage,
                provider=provider,
                dataset=result.dataset,
                result=result,
            )
            raw_id = raw.id
            if run.raw_object_id is None:
                run.raw_object_id = raw.id
        for observation in result.observations:
            key = (observation.source_series_id, observation.period_start, observation.vintage_at)
            previous = staged_by_key.get(key)
            if previous is not None and (
                previous[0].value,
                previous[0].value_text,
                previous[0].status,
            ) != (observation.value, observation.value_text, observation.status):
                await _quarantine(
                    session,
                    run=run,
                    code="conflicting_provider_snapshot",
                    message=(
                        "Provider returned contradictory rows for "
                        f"source_series_id={observation.source_series_id}, "
                        f"period={observation.period_start}, "
                        f"vintage={observation.vintage_at.isoformat()}."
                    ),
                )
                raise RuntimeError("Provider snapshot contains contradictory duplicate rows")
            staged_by_key.setdefault(key, (observation, raw_id))
    staged = list(staged_by_key.values())

    issues, completeness_metrics = validate_ingestion_completeness(
        mapping_pairs,
        [observation for observation, _raw_id in staged],
        mode=mode,
    )
    observed_source_ids = {
        observation.source_series_id for observation, _raw_id in staged
    }
    missing_source_ids = resolved_ids - observed_source_ids
    tradingview_symbol_errors = (
        adapter.symbol_errors if isinstance(adapter, TradingViewAdapter) else {}
    )
    source_by_id = {source.id: source for source, _dataset in mapping_pairs}
    symbol_errors: list[dict[str, Any]] = [
        {
            "source_series_id": source_id,
            "provider_series_id": source_by_id[source_id].provider_series_id,
            "error": tradingview_symbol_errors.get(
                str(source_by_id[source_id].provider_series_id),
                "TradingView returned no valid latest observation",
            ),
        }
        for source_id in sorted(missing_source_ids)
    ]
    blocking_issues = []
    for issue in issues:
        if (
            ingestion_issue_severity(
                provider_code,
                issue,
                missing_source_ids,
                mode=mode,
            )
            == "warning"
        ):
            session.add(
                QualityResult(
                    run_id=run.id,
                    rule_code=issue.code,
                    severity="warning",
                    passed=False,
                    period_start=issue.period_start,
                    message=(
                        f"source_series_id={issue.source_series_id}: {issue.message}"
                    ),
                )
            )
        else:
            blocking_issues.append(issue)
    run.metrics = {
        "fetch_result_count": len(results),
        "staged_observation_count": len(staged),
        "requested_source_series_count": len(mapping_pairs),
        "observed_source_series_count": len(observed_source_ids),
        "failed_source_series_count": len(missing_source_ids),
        **completeness_metrics,
    }
    if blocking_issues:
        for issue in blocking_issues:
            session.add(
                QualityResult(
                    run_id=run.id,
                    rule_code=issue.code,
                    severity="blocking",
                    passed=False,
                    period_start=issue.period_start,
                    message=issue.message,
                )
            )
        run.status = "quarantined"
        run.error_code = "provider_completeness_failed"
        run.error_message = (
            f"Provider completeness gate failed with {len(blocking_issues)} blocking issue(s); "
            "nothing was published."
        )
        run.finished_at = datetime.now(UTC)
        await session.commit()
        raise RuntimeError(run.error_message)
    coverage = float(cast(str | float, completeness_metrics["coverage_ratio"]))

    previous = await session.scalar(
        select(PublicationBatch)
        .where(PublicationBatch.provider_id == provider.id, PublicationBatch.status == "active")
        .order_by(PublicationBatch.activated_at.desc())
        .limit(1)
    )
    batch = PublicationBatch(
        provider_id=provider.id,
        run_id=run.id,
        previous_batch_id=previous.id if previous else None,
        status="building",
    )
    session.add(batch)
    await session.flush()

    counts = {"inserted": 0, "revised": 0, "unchanged": 0, "rejected": 0}
    rejected_items: list[dict[str, object | None]] = []
    publication_savepoint = await session.begin_nested()
    for observation, raw_id in staged:
        item_savepoint = await session.begin_nested()
        try:
            outcome = await _merge_observation(
                session,
                observation,
                run_id=run.id,
                raw_object_id=raw_id,
                publication_batch_id=batch.id,
            )
            await item_savepoint.commit()
            counts[outcome] += 1
        except Exception as exc:
            await item_savepoint.rollback()
            counts["rejected"] += 1
            # Keep the diagnostic outside the publication savepoint. Otherwise the
            # rollback that protects atomic publication also erases the root cause.
            rejected_items.append(
                {
                    "period_start": observation.period_start,
                    "actual_value": observation.value_text
                    or (str(observation.value) if observation.value is not None else None),
                    "message": f"Observation rejected: {type(exc).__name__}: {exc}",
                }
            )

    if counts["rejected"] or counts["inserted"] + counts["revised"] + counts["unchanged"] == 0:
        await publication_savepoint.rollback()
        for item in rejected_items:
            session.add(
                QualityResult(
                    run_id=run.id,
                    rule_code="observation_merge",
                    severity="blocking",
                    passed=False,
                    period_start=item["period_start"],
                    actual_value=item["actual_value"],
                    message=str(item["message"]),
                )
            )
        batch.status = "failed"
        batch.summary = counts
        run.status = "quarantined"
        run.error_code = "publication_atomicity"
        run.error_message = "At least one observation failed; no latest values were published."
        session.add(
            QualityResult(
                run_id=run.id,
                rule_code="publication_atomicity",
                severity="blocking",
                passed=False,
                actual_value=str(counts["rejected"]),
                expected_value="0",
                message=run.error_message,
            )
        )
    else:
        await publication_savepoint.commit()
        now = datetime.now(UTC)
        if previous:
            previous.status = "superseded"
        batch.status = "active"
        batch.activated_at = now
        batch.summary = {**counts, "coverage_ratio": coverage}
        run.status = "succeeded"

    run.inserted_count = counts["inserted"]
    run.revised_count = counts["revised"]
    run.unchanged_count = counts["unchanged"]
    run.rejected_count = counts["rejected"]
    run.finished_at = datetime.now(UTC)

    if run.status == "succeeded":
        for source, _dataset in mapping_rows:
            bounds = (
                await session.execute(
                    select(
                        ObservationLatest.source_series_id,
                        func.min(ObservationLatest.period_start),
                        func.max(ObservationLatest.period_start),
                    )
                    .where(ObservationLatest.source_series_id == source.id)
                    .group_by(ObservationLatest.source_series_id)
                )
            ).first()
            if bounds:
                series = await session.get(Series, source.series_id)
                if series:
                    series.first_period = bounds[1]
                    series.latest_period = bounds[2]
    await session.commit()
    if run.status != "succeeded":
        raise RuntimeError(run.error_message or "Publication was quarantined")
    return {
        **counts,
        "staged_observation_count": len(staged),
        "requested_count": len(mapping_pairs),
        "succeeded_count": len(observed_source_ids),
        "failed_count": len(missing_source_ids),
        "symbol_errors": symbol_errors,
        "status": (
            "partial_success"
            if missing_source_ids and provider_code == TradingViewAdapter.code
            else run.status
        ),
        "batch_id": str(batch.id),
        "source_series_count": len(resolved_ids),
    }
