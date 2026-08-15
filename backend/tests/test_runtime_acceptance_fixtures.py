import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from macrolens_api import test_fixtures
from macrolens_api.models import Job


def test_runtime_acceptance_fixtures_reject_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("ALLOW_TEST_FIXTURES", "true")
    test_fixtures.get_settings.cache_clear()

    with pytest.raises(RuntimeError, match="disabled outside an explicit test environment"):
        asyncio.run(
            test_fixtures.seed_runtime_acceptance_fixtures(  # type: ignore[arg-type]
                SimpleNamespace()
            )
        )

    test_fixtures.get_settings.cache_clear()


def test_clean_seed_mappings_receive_fixture_probe_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sources = [
        SimpleNamespace(
            id=index,
            series_id=uuid4(),
            provider_series_id=f"SERIES-{index}",
            source_locator={"fixture": index},
            mapping_type="direct",
            source_frequency="monthly",
            source_unit="index",
            source_seasonal_adjustment=None,
            mapping_status="needs_review",
            is_primary=False,
        )
        for index in range(1, 4)
    ]
    rows = [
        (
            source,
            SimpleNamespace(status="active"),
            SimpleNamespace(id=source.id, code=f"DATASET-{source.id}"),
            SimpleNamespace(code="BLS_API_V2"),
        )
        for source in sources
    ]

    class FakeSession:
        def __init__(self) -> None:
            self.added: list[object] = []

        def add(self, value: object) -> None:
            self.added.append(value)

        async def flush(self) -> None:
            return None

    approvals: list[int] = []

    async def approve_mapping(
        _session: object,
        *,
        source_series_id: int,
        probe_job_id: object,
        verified_by: str,
    ) -> object:
        assert probe_job_id is not None
        assert verified_by == "runtime-acceptance-fixture"
        approvals.append(source_series_id)
        source = sources[source_series_id - 1]
        source.mapping_status = "verified"
        source.is_primary = True
        return source

    monkeypatch.setattr(test_fixtures, "approve_mapping_from_probe", approve_mapping)
    session = FakeSession()

    asyncio.run(
        test_fixtures._approve_runtime_acceptance_mappings(  # type: ignore[arg-type]
            session,
            rows,  # type: ignore[arg-type]
        )
    )

    jobs = [item for item in session.added if isinstance(item, Job)]
    assert approvals == [1, 2, 3]
    assert len(jobs) == 3
    assert all(job.job_type == "mapping_probe" and job.status == "succeeded" for job in jobs)
    assert all(job.payload.get("fixture") is True for job in jobs)
    assert all(job.result.get("classification") == "PASS" for job in jobs)
    assert all(source.mapping_status == "verified" and source.is_primary for source in sources)
