from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from macrolens_api.models import IngestionRun
from macrolens_worker.tasks.sync import sync_provider


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

    async def scalar(self, _statement: object) -> SimpleNamespace:
        return SimpleNamespace(id=1)

    async def execute(self, _statement: object) -> _MappingRows:
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
