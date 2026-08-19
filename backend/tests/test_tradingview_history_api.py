from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from macrolens_api.errors import AppError
from macrolens_api.routers import admin as admin_router


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


def _job(payload: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        job_type="sync_provider",
        status="queued",
        priority=12,
        payload=payload,
        attempts=0,
        max_attempts=3,
        last_error=None,
        result={},
        created_at=datetime.now(UTC),
        started_at=None,
        finished_at=None,
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
