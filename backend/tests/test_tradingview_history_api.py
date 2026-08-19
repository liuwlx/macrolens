from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from macrolens_api.errors import AppError
from macrolens_api.routers import admin as admin_router
from macrolens_api.schemas import HistoryBatchCreate
from macrolens_api.services.jobs import JobReservation, reserve_jobs


class _ScalarRows:
    def __init__(self, rows: list[object]) -> None:
        self._rows = rows

    def all(self) -> list[object]:
        return self._rows


class _Session:
    def __init__(
        self,
        provider: object,
        source: object,
        active_jobs: list[object] | None = None,
    ) -> None:
        self._scalars = iter([provider, source])
        self._active_jobs = active_jobs or []

    async def scalar(self, _statement: object) -> object:
        return next(self._scalars)

    async def scalars(self, _statement: object) -> _ScalarRows:
        return _ScalarRows(self._active_jobs)


def _job(
    payload: dict[str, object],
    *,
    status: str = "queued",
    result: dict[str, object] | None = None,
    last_error: str | None = None,
    job_type: str = "sync_provider",
    idempotency_key: str = "test-key",
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        job_type=job_type,
        status=status,
        priority=12,
        payload=payload,
        idempotency_key=idempotency_key,
        attempts=0,
        max_attempts=3,
        last_error=last_error,
        result=result or {},
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
    )


class _BatchSession:
    def __init__(
        self,
        *,
        provider: object,
        eligible: list[tuple[int, str]],
        completed_jobs: list[object] | None = None,
    ) -> None:
        self._scalar_rows = iter([provider, None, None])
        self.eligible = eligible
        self.completed_jobs = completed_jobs or []
        self.commits = 0
        self.statements: list[object] = []

    async def scalar(self, statement: object) -> object:
        self.statements.append(statement)
        return next(self._scalar_rows)

    async def execute(self, statement: object) -> object:
        self.statements.append(statement)
        if "pg_advisory_xact_lock" in str(statement):
            return SimpleNamespace()
        return SimpleNamespace(all=lambda: self.eligible)

    async def scalars(self, statement: object) -> _ScalarRows:
        self.statements.append(statement)
        return _ScalarRows(self.completed_jobs)

    async def commit(self) -> None:
        self.commits += 1


def test_history_batch_enqueues_remaining_sources_in_frequency_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = _job(
        {
            "provider_code": "TRADINGVIEW_WEB",
            "mode": "backfill",
            "source_series_ids": [2],
        }
    )
    completed.status = "succeeded"
    session = _BatchSession(
        provider=SimpleNamespace(id=11),
        eligible=[
            (6, "daily"),
            (1, "monthly"),
            (4, "weekly"),
            (3, "annual"),
            (2, "monthly"),
            (5, "quarterly"),
        ],
        completed_jobs=[completed],
    )
    captured: list[JobReservation] = []

    async def fake_reserve_many(
        _session: object, reservations: list[JobReservation]
    ) -> list[object]:
        captured.extend(reservations)
        return [_job(reservation.payload) for reservation in reservations]

    monkeypatch.setattr(admin_router, "reserve_jobs", fake_reserve_many)
    request = HistoryBatchCreate(idempotency_key="manual-run-20260820")
    result = asyncio.run(
        admin_router.create_provider_history_batch(
            "TRADINGVIEW_WEB",
            request,
            session,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )

    assert result.status == "queued"
    assert result.total == 6
    assert result.candidate_count == 5
    assert result.skipped_completed == 1
    assert result.queued == 5
    assert result.running == result.succeeded == result.failed == 0
    assert session.commits == 1
    assert [item.payload["source_series_ids"] for item in captured] == [
        [3],
        [5],
        [1],
        [4],
        [6],
    ]
    assert {item.priority for item in captured} == {5}
    assert {item.max_attempts for item in captured} == {1}
    assert {item.job_type for item in captured} == {"sync_provider"}
    digest = hashlib.sha256(request.idempotency_key.encode()).hexdigest()
    assert [item.idempotency_key for item in captured] == [
        f"manual-history-batch:{digest}:{source_id}"
        for source_id in [3, 5, 1, 4, 6]
    ]
    assert {item.payload["history_batch_id"] for item in captured} == {str(result.batch_id)}
    assert all(
        item.payload["history_batch"]
        == {
            "total": 6,
            "candidate_count": 5,
            "skipped_completed": 1,
            "selected_count": 5,
            "limit": 500,
            "request_key_sha256": digest,
        }
        for item in captured
    )


def test_history_batch_default_limit_enqueues_all_339_remaining_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = _job(
        {
            "provider_code": "TRADINGVIEW_WEB",
            "mode": "backfill",
            "source_series_ids": [1],
        },
        status="succeeded",
    )
    session = _BatchSession(
        provider=SimpleNamespace(id=11),
        eligible=[(source_id, "monthly") for source_id in range(1, 341)],
        completed_jobs=[completed],
    )
    captured: list[JobReservation] = []

    async def fake_reserve_many(
        _session: object, reservations: list[JobReservation]
    ) -> list[object]:
        captured.extend(reservations)
        return [_job(reservation.payload) for reservation in reservations]

    monkeypatch.setattr(admin_router, "reserve_jobs", fake_reserve_many)
    result = asyncio.run(
        admin_router.create_provider_history_batch(
            "TRADINGVIEW_WEB",
            HistoryBatchCreate(idempotency_key="enqueue-all-remaining-339"),
            session,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )

    assert result.total == 340
    assert result.candidate_count == result.queued == len(captured) == 339
    assert result.skipped_completed == 1
    assert captured[0].payload["source_series_ids"] == [2]
    assert captured[-1].payload["source_series_ids"] == [340]
    assert {item.priority for item in captured} == {5}
    assert {item.max_attempts for item in captured} == {1}


def test_history_batch_reuses_active_batch_after_taking_advisory_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    batch_id = uuid4()
    active = _job(
        {
            "provider_code": "TRADINGVIEW_WEB",
            "mode": "backfill",
            "source_series_ids": [42],
            "history_batch_id": str(batch_id),
            "history_batch": {
                "total": 2,
                "candidate_count": 2,
                "skipped_completed": 0,
                "selected_count": 2,
            },
        }
    )
    session = _BatchSession(
        provider=SimpleNamespace(id=11),
        eligible=[],
        completed_jobs=[active],
    )
    session._scalar_rows = iter([SimpleNamespace(id=11), None, active])

    async def unexpected_reserve(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("an active history batch must be reused")

    replay_markers: list[object] = []

    async def fake_reserve_marker(
        _session: object, **kwargs: object
    ) -> tuple[object, bool]:
        marker = _job(
            kwargs["payload"],  # type: ignore[arg-type]
            job_type=str(kwargs["job_type"]),
            idempotency_key=str(kwargs["idempotency_key"]),
        )
        replay_markers.append(marker)
        return marker, True

    monkeypatch.setattr(admin_router, "reserve_jobs", unexpected_reserve)
    monkeypatch.setattr(admin_router, "reserve_job", fake_reserve_marker)
    request = HistoryBatchCreate(idempotency_key="another-admin-request")
    result = asyncio.run(
        admin_router.create_provider_history_batch(
            "TRADINGVIEW_WEB",
            request,
            session,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )

    assert result.batch_id == batch_id
    assert result.status == "queued"
    assert session.commits == 1
    assert any("pg_advisory_xact_lock" in str(item) for item in session.statements)
    assert len(replay_markers) == 1
    marker = replay_markers[0]
    digest = hashlib.sha256(request.idempotency_key.encode()).hexdigest()
    assert marker.job_type == "history_batch_marker"
    assert marker.status == "succeeded"
    assert marker.finished_at is not None
    assert marker.payload["history_batch_id"] == str(batch_id)
    assert marker.payload["history_request_key_sha256"] == digest
    assert marker.idempotency_key == f"manual-history-batch:{digest}:active-reuse"

    replay_session = _BatchSession(
        provider=SimpleNamespace(id=11),
        eligible=[],
        completed_jobs=[active, marker],
    )
    replay_session._scalar_rows = iter([SimpleNamespace(id=11), marker])
    replay = asyncio.run(
        admin_router.create_provider_history_batch(
            "TRADINGVIEW_WEB",
            request,
            replay_session,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )
    assert replay.batch_id == batch_id
    assert replay_session.commits == 0


def test_history_batch_replays_the_same_request_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = HistoryBatchCreate(idempotency_key="stable-client-request")
    digest = hashlib.sha256(request.idempotency_key.encode()).hexdigest()
    batch_id = uuid4()
    replay = _job(
        {
            "provider_code": "TRADINGVIEW_WEB",
            "mode": "backfill",
            "source_series_ids": [42],
            "history_batch_id": str(batch_id),
            "history_request_key_sha256": digest,
            "history_batch": {
                "total": 1,
                "candidate_count": 1,
                "skipped_completed": 0,
                "selected_count": 1,
            },
        },
        status="succeeded",
        result={"inserted": 12, "staged_observation_count": 12},
    )
    session = _BatchSession(
        provider=SimpleNamespace(id=11),
        eligible=[],
        completed_jobs=[replay],
    )
    session._scalar_rows = iter([SimpleNamespace(id=11), replay])

    async def unexpected_reserve(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the same request key must replay its durable batch")

    monkeypatch.setattr(admin_router, "reserve_jobs", unexpected_reserve)
    result = asyncio.run(
        admin_router.create_provider_history_batch(
            "TRADINGVIEW_WEB",
            request,
            session,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )

    assert result.batch_id == batch_id
    assert result.status == "succeeded"
    assert result.inserted == result.staged_observation_count == 12
    assert session.commits == 0


class _GetSession:
    def __init__(self, jobs: list[object]) -> None:
        self.jobs = jobs
        self.statement: object | None = None

    async def scalars(self, statement: object) -> _ScalarRows:
        self.statement = statement
        return _ScalarRows(self.jobs)


def test_history_batch_get_aggregates_terminal_results_and_failures() -> None:
    batch_id = uuid4()
    metadata = {
        "total": 4,
        "candidate_count": 3,
        "skipped_completed": 1,
        "selected_count": 3,
    }

    def payload(source_id: int) -> dict[str, object]:
        return {
            "provider_code": "TRADINGVIEW_WEB",
            "mode": "backfill",
            "source_series_ids": [source_id],
            "history_batch_id": str(batch_id),
            "history_batch": metadata,
        }

    succeeded = _job(
        payload(10),
        status="succeeded",
        result={
            "inserted": 7,
            "revised": 2,
            "unchanged": 3,
            "staged_observation_count": 12,
            "failed_count": 0,
            "status": "succeeded",
        },
    )
    failed = _job(payload(11), status="failed", last_error="RuntimeError: history gap")
    logical_failure = _job(
        payload(12),
        status="succeeded",
        result={
            "failed_count": 1,
            "status": "partial_success",
            "symbol_errors": [{"source_series_id": 12, "error": "no valid points"}],
        },
    )
    session = _GetSession([succeeded, failed, logical_failure])

    result = asyncio.run(
        admin_router.get_provider_history_batch(
            "TRADINGVIEW_WEB",
            batch_id,
            session,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )

    assert result.status == "partial_failure"
    assert result.total == 4
    assert result.candidate_count == 3
    assert result.skipped_completed == 1
    assert result.succeeded == 1
    assert result.failed == 2
    assert (result.inserted, result.revised, result.unchanged) == (7, 2, 3)
    assert result.staged_observation_count == 12
    assert [(item.source_series_id, item.error) for item in result.failures] == [
        (11, "RuntimeError: history gap"),
        (12, "no valid points"),
    ]
    assert session.statement is not None
    assert " LIMIT " not in str(session.statement).upper()


def test_history_batch_persists_an_empty_result(monkeypatch: pytest.MonkeyPatch) -> None:
    completed = _job(
        {
            "provider_code": "TRADINGVIEW_WEB",
            "mode": "backfill",
            "source_series_ids": [42],
        },
        status="succeeded",
    )
    session = _BatchSession(
        provider=SimpleNamespace(id=11),
        eligible=[(42, "monthly")],
        completed_jobs=[completed],
    )

    async def fake_reserve_marker(_session: object, **kwargs: object) -> tuple[object, bool]:
        marker = _job(
            kwargs["payload"],  # type: ignore[arg-type]
            job_type=str(kwargs["job_type"]),
            idempotency_key=str(kwargs["idempotency_key"]),
        )
        return marker, True

    monkeypatch.setattr(admin_router, "reserve_job", fake_reserve_marker)
    result = asyncio.run(
        admin_router.create_provider_history_batch(
            "TRADINGVIEW_WEB",
            HistoryBatchCreate(idempotency_key="everything-completed"),
            session,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )

    assert result.status == "empty"
    assert result.total == 1
    assert result.candidate_count == 0
    assert result.skipped_completed == 1
    assert result.queued == result.running == result.succeeded == result.failed == 0
    assert session.commits == 1


def test_reserve_jobs_uses_one_bulk_insert_without_committing() -> None:
    reservations = [
        JobReservation("sync_provider", {"source_series_ids": [1]}, "batch:1", 5, 1),
        JobReservation("sync_provider", {"source_series_ids": [2]}, "batch:2", 5, 1),
    ]
    jobs = [
        _job(item.payload, idempotency_key=item.idempotency_key)
        for item in reversed(reservations)
    ]

    class _ReserveSession:
        def __init__(self) -> None:
            self.executed: list[object] = []

        async def execute(self, statement: object) -> None:
            self.executed.append(statement)

        async def scalars(self, _statement: object) -> _ScalarRows:
            return _ScalarRows(jobs)

    session = _ReserveSession()
    result = asyncio.run(reserve_jobs(session, reservations))  # type: ignore[arg-type]

    assert [job.idempotency_key for job in result] == ["batch:1", "batch:2"]
    assert len(session.executed) == 1
    assert "ON CONFLICT" in str(session.executed[0])


def test_history_batch_rejects_other_providers() -> None:
    with pytest.raises(AppError, match="不支持的历史同步"):
        asyncio.run(
            admin_router.create_provider_history_batch(
                "FRED_API",
                HistoryBatchCreate(idempotency_key="not-tradingview"),
                object(),  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
            )
        )


def test_history_endpoint_enqueues_one_scoped_backfill(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = SimpleNamespace(id=11)
    source = SimpleNamespace(id=42)
    queued: dict[str, object] = {}

    async def fake_enqueue(_session: object, **kwargs: object) -> SimpleNamespace:
        queued.update(kwargs)
        return _job(kwargs["payload"])  # type: ignore[arg-type]

    monkeypatch.setattr(admin_router, "enqueue_job", fake_enqueue)
    result = asyncio.run(
        admin_router.sync_series_history_manually(
            "TRADINGVIEW_WEB",
            uuid4(),
            _Session(provider, source),  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )

    assert result.status == "queued"
    assert queued["job_type"] == "sync_provider"
    assert queued["payload"] == {
        "provider_code": "TRADINGVIEW_WEB",
        "mode": "backfill",
        "source_series_ids": [42],
    }
    assert str(queued["idempotency_key"]).startswith("manual-history:TRADINGVIEW_WEB:42:")


def test_history_endpoint_returns_active_history_job(monkeypatch: pytest.MonkeyPatch) -> None:
    source = SimpleNamespace(id=42)
    active = _job(
        {
            "provider_code": "TRADINGVIEW_WEB",
            "mode": "backfill",
            "source_series_ids": [42],
        }
    )

    async def unexpected_enqueue(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("active history job should be reused")

    monkeypatch.setattr(admin_router, "enqueue_job", unexpected_enqueue)
    result = asyncio.run(
        admin_router.sync_series_history_manually(
            "TRADINGVIEW_WEB",
            uuid4(),
            _Session(SimpleNamespace(id=11), source, [active]),  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
        )
    )
    assert result.id == active.id


def test_history_endpoint_rejects_other_providers() -> None:
    with pytest.raises(AppError, match="不支持的历史同步"):
        asyncio.run(
            admin_router.sync_series_history_manually(
                "FRED_API",
                uuid4(),
                _Session(SimpleNamespace(id=11), SimpleNamespace(id=42)),  # type: ignore[arg-type]
                None,  # type: ignore[arg-type]
            )
        )
