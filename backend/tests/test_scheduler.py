from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime
from types import ModuleType

import pytest


def test_fomc_meeting_dates_support_cross_month_and_cross_year_ranges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage = ModuleType("macrolens_api.services.storage")
    setattr(storage, "ObjectStorage", object)
    monkeypatch.setitem(sys.modules, "macrolens_api.services.storage", storage)
    from macrolens_worker.tasks.fomc import _meeting_dates

    assert _meeting_dates(2024, "Apr/May", "30-1") == (
        date(2024, 4, 30),
        date(2024, 5, 1),
    )
    assert _meeting_dates(2024, "Dec/Jan", "31-1") == (
        date(2024, 12, 31),
        date(2025, 1, 1),
    )


class _ScalarResult:
    def __init__(self, values: set[str]) -> None:
        self._values = values

    def all(self) -> list[str]:
        return list(self._values)


class _FakeSession:
    def __init__(self, active_providers: set[str]) -> None:
        self.active_providers = active_providers

    async def __aenter__(self) -> _FakeSession:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None

    async def scalar(self, _statement: object) -> int:
        return 0

    async def scalars(self, _statement: object) -> _ScalarResult:
        return _ScalarResult(self.active_providers)

    async def rollback(self) -> None:
        return None


@pytest.mark.parametrize(
    ("active_providers", "expected_jobs"),
    [
        ({"FEDERAL_RESERVE"}, ["sync_fomc_calendar", "evaluate_alerts"]),
        ({"BLS_API_V2"}, ["sync_bls_release_calendar", "evaluate_alerts"]),
        (
            {"BLS_API_V2", "FEDERAL_RESERVE"},
            ["sync_fomc_calendar", "sync_bls_release_calendar", "evaluate_alerts"],
        ),
        (set(), ["evaluate_alerts"]),
    ],
)
def test_calendar_jobs_follow_provider_active_state(
    monkeypatch: pytest.MonkeyPatch,
    active_providers: set[str],
    expected_jobs: list[str],
) -> None:
    from macrolens_worker import scheduler

    session = _FakeSession(active_providers)
    queued_jobs: list[str] = []

    async def fake_enqueue_job(
        _session: object,
        *,
        job_type: str,
        **_kwargs: object,
    ) -> None:
        queued_jobs.append(job_type)

    monkeypatch.setattr(scheduler, "SessionLocal", lambda: session)
    monkeypatch.setattr(scheduler, "enqueue_job", fake_enqueue_job)

    result = asyncio.run(
        scheduler.enqueue_schedule_tick(datetime(2026, 8, 3, tzinfo=UTC))
    )

    assert queued_jobs == expected_jobs
    assert result == {"queued": len(expected_jobs)}
