from __future__ import annotations

import asyncio
from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from macrolens_api.models import IngestionRun
from macrolens_worker.tasks.ingestion_quality import CompletenessIssue
from macrolens_worker.tasks.sync import ingestion_issue_severity, sync_provider


class _StopBeforeFetch(Exception):
    pass


class _MappingRows:
    def __init__(self, source_ids: list[int]) -> None:
        dataset = SimpleNamespace(id=1)
        self.rows = [
            (SimpleNamespace(id=source_id), dataset) for source_id in source_ids
        ]

    def tuples(self) -> _MappingRows:
        return self

    def all(self) -> list[tuple[SimpleNamespace, SimpleNamespace]]:
        return self.rows


class _RunCaptureSession:
    def __init__(self, source_ids: list[int]) -> None:
        self.source_ids = source_ids
        self.added: list[object] = []
        self.executed_sql: list[str] = []

    async def scalar(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(id=1)

    async def execute(self, statement: object) -> object:
        sql = str(statement)
        self.executed_sql.append(sql)
        if "pg_advisory_xact_lock" in sql:
            return SimpleNamespace()
        return _MappingRows(self.source_ids)

    def add(self, value: object) -> None:
        self.added.append(value)

    async def flush(self) -> None:
        raise _StopBeforeFetch


def _capture_business_key(source_ids: list[int], job_id: UUID) -> str:
    session = _RunCaptureSession(source_ids)
    with pytest.raises(_StopBeforeFetch):
        asyncio.run(
            sync_provider(  # type: ignore[arg-type]
                session,
                provider_code="TRADINGVIEW_WEB",
                mode="latest",
                job_id=job_id,
            )
        )
    run = next(item for item in session.added if isinstance(item, IngestionRun))
    return run.business_key


def test_large_sync_scope_produces_bounded_collision_resistant_business_key() -> None:
    job_id = uuid4()
    first = _capture_business_key(list(range(1, 341)), job_id)
    second = _capture_business_key([*range(1, 340), 341], job_id)
    max_length = IngestionRun.__table__.c.business_key.type.length

    assert max_length == 300
    assert len(first) <= max_length
    assert len(second) <= max_length
    assert first != second
    assert first.endswith(str(job_id))
    assert second.endswith(str(job_id))


def test_tradingview_backfill_acquires_provider_transaction_lock() -> None:
    session = _RunCaptureSession([42])

    with pytest.raises(_StopBeforeFetch):
        asyncio.run(
            sync_provider(  # type: ignore[arg-type]
                session,
                provider_code="TRADINGVIEW_WEB",
                mode="backfill",
                job_id=uuid4(),
                source_series_ids=[42],
            )
        )

    assert any("pg_advisory_xact_lock" in sql for sql in session.executed_sql)

    latest_session = _RunCaptureSession([42])
    with pytest.raises(_StopBeforeFetch):
        asyncio.run(
            sync_provider(  # type: ignore[arg-type]
                latest_session,
                provider_code="TRADINGVIEW_WEB",
                mode="latest",
                job_id=uuid4(),
                source_series_ids=[42],
            )
        )
    assert not any(
        "pg_advisory_xact_lock" in sql for sql in latest_session.executed_sql
    )


def test_tradingview_stale_latest_value_is_a_warning_without_weakening_other_gates() -> None:
    stale = CompletenessIssue(
        code="stale_latest_period",
        message="The provider's latest available period is historical.",
        source_series_id=42,
    )
    conflict = CompletenessIssue(
        code="conflicting_duplicate",
        message="Two values disagree.",
        source_series_id=42,
    )

    assert ingestion_issue_severity(
        "TRADINGVIEW_WEB", stale, set(), mode="incremental"
    ) == "warning"
    assert ingestion_issue_severity(
        "TRADINGVIEW_WEB", conflict, set(), mode="incremental"
    ) == "blocking"
    assert (
        ingestion_issue_severity("FRED_API", stale, set(), mode="incremental")
        == "blocking"
    )


@pytest.mark.parametrize(
    (
        "provider_code",
        "mode",
        "source_frequency",
        "provider_series_id",
        "period_start",
        "missing_period_count",
        "expected",
    ),
    [
        (
            "TRADINGVIEW_WEB",
            "backfill",
            "weekly",
            "ECONOMICS:WEEKLY_GAP",
            date(2025, 10, 3),
            21,
            "warning",
        ),
        (
            "TRADINGVIEW_WEB",
            "backfill",
            "monthly",
            "ECONOMICS:MONTHLY_GAP",
            date(2025, 10, 1),
            46,
            "warning",
        ),
        (
            "TRADINGVIEW_WEB",
            "backfill",
            "quarterly",
            "ECONOMICS:QUARTERLY_GAP",
            date(2025, 10, 1),
            3,
            "warning",
        ),
        (
            "TRADINGVIEW_WEB",
            "backfill",
            "annual",
            "ECONOMICS:ANNUAL_GAP",
            date(2025, 1, 1),
            4,
            "warning",
        ),
        (
            "TRADINGVIEW_WEB",
            "backfill",
            "daily",
            "ECONOMICS:DAILY_GAP",
            date(2025, 10, 1),
            1,
            "blocking",
        ),
        (
            "TRADINGVIEW_WEB",
            "incremental",
            "monthly",
            "ECONOMICS:MONTHLY_GAP",
            date(2025, 10, 1),
            1,
            "blocking",
        ),
        (
            "TRADINGVIEW_WEB",
            "vintage_backfill",
            "monthly",
            "ECONOMICS:MONTHLY_GAP",
            date(2025, 10, 1),
            1,
            "blocking",
        ),
        (
            "FRED_API",
            "backfill",
            "monthly",
            "ECONOMICS:MONTHLY_GAP",
            date(2025, 10, 1),
            1,
            "blocking",
        ),
        (
            "TRADINGVIEW_WEB",
            "backfill",
            None,
            "ECONOMICS:UNKNOWN_FREQUENCY",
            date(2025, 10, 1),
            1,
            "blocking",
        ),
    ],
    ids=[
        "weekly-backfill-gap",
        "monthly-backfill-gap",
        "quarterly-backfill-gap",
        "annual-backfill-gap",
        "daily-backfill-gap",
        "incremental",
        "vintage-backfill",
        "other-provider",
        "unknown-frequency",
    ],
)
def test_history_gap_severity_depends_on_provider_mode_and_frequency(
    provider_code: str,
    mode: str,
    source_frequency: str | None,
    provider_series_id: str,
    period_start: date,
    missing_period_count: int,
    expected: str,
) -> None:
    issue = CompletenessIssue(
        code="history_gap",
        message="TradingView omitted monthly history.",
        source_series_id=42,
        provider_series_id=provider_series_id,
        period_start=period_start,
        missing_period_count=missing_period_count,
        source_frequency=source_frequency,
    )

    assert ingestion_issue_severity(provider_code, issue, set(), mode=mode) == expected
