from __future__ import annotations

import json
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from macrolens_api.config import get_settings
from macrolens_worker.providers.bls import BLSAdapter

FIXTURE = Path(__file__).parent / "fixtures/bls/cpi_headline_2025.json"
TITLE = "All items in U.S. city average, all urban consumers, seasonally adjusted"


def _source(source_id: int = 42) -> SimpleNamespace:
    return SimpleNamespace(
        id=source_id,
        provider_series_id="CUSR0000SA0",
        source_frequency="monthly",
        source_locator={
            "start_year": 1947,
            "expected_first_period": "1947-01-01",
            "expected_catalog_title": TITLE,
        },
    )


def _dataset() -> SimpleNamespace:
    return SimpleNamespace(id=7, code="Public Data API")


def _provider() -> SimpleNamespace:
    return SimpleNamespace(id=3, code="BLS_API_V2")


async def test_mapping_probe_distinguishes_business_success_identity_and_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    get_settings.cache_clear()
    body = json.loads(FIXTURE.read_text(encoding="utf-8"))["responses"][0]

    async def handler(request: httpx.Request) -> httpx.Response:
        request_payload = json.loads(request.content)
        assert request_payload["seriesid"] == ["CUSR0000SA0"]
        assert "registrationkey" not in request_payload
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/json"},
            json=body,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BLSAdapter(client).probe(_provider(), _source(), _dataset())

    assert result.http_reachable is True
    assert result.http_status == 200
    assert result.business_success is True
    assert result.identity_match is True
    assert result.provider_series_id == "CUSR0000SA0"
    assert result.official_description == TITLE
    assert result.authorization_available is False
    assert result.production_ready is False
    assert result.classification == "AUTH_REQUIRED"
    assert len(result.response_sha256) == 64
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"status": "REQUEST_FAILED"}, "business status"),
        ({"Results": {"series": []}}, "coverage mismatch"),
    ],
)
async def test_mapping_probe_fails_closed_on_business_or_identity_drift(
    monkeypatch: pytest.MonkeyPatch,
    mutation: dict[str, object],
    message: str,
) -> None:
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    get_settings.cache_clear()
    body = json.loads(FIXTURE.read_text(encoding="utf-8"))["responses"][0]
    body.update(mutation)

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BLSAdapter(client).probe(_provider(), _source(), _dataset())
    assert result.classification == "BLOCKED"
    assert result.production_ready is False
    if message == "business status":
        assert result.business_success is False
    else:
        assert result.business_success is True
        assert result.identity_match is False
    get_settings.cache_clear()


async def test_mapping_probe_records_transport_and_http_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    get_settings.cache_clear()

    async def unreachable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(unreachable)) as client:
        transport_result = await BLSAdapter(client).probe(
            _provider(), _source(), _dataset()
        )
    assert transport_result.http_reachable is False
    assert transport_result.http_status is None
    assert transport_result.classification == "BLOCKED"

    async def unavailable(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, request=request, content=b"temporarily unavailable")

    async with httpx.AsyncClient(transport=httpx.MockTransport(unavailable)) as client:
        http_result = await BLSAdapter(client).probe(_provider(), _source(), _dataset())
    assert http_result.http_reachable is True
    assert http_result.http_status == 503
    assert http_result.business_success is False
    assert len(http_result.response_sha256) == 64
    get_settings.cache_clear()


def test_offline_replay_uses_provider_parser_and_preserves_sanitized_raw_lineage() -> None:
    raw = FIXTURE.read_bytes()
    result = BLSAdapter.replay(
        _provider(),
        [(_source(), _dataset())],
        raw,
        vintage_at=datetime(2026, 1, 13, 13, 30, tzinfo=UTC),
    )

    assert result.raw_bytes == raw
    assert b"registrationkey" not in result.raw_bytes
    assert b"test-key" not in result.raw_bytes
    assert result.request_parameters == {
        "requests": [json.loads(raw)["requests"][0]]
    }
    assert [str(item.value) for item in result.observations] == ["324.003", "324.054"]
    assert all(item.source_series_id == 42 for item in result.observations)
    assert all(
        item.vintage_at == datetime(2026, 1, 13, 13, 30, tzinfo=UTC)
        for item in result.observations
    )


async def test_fetch_never_persists_bls_registration_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BLS_API_KEY", "do-not-persist-this-key")
    get_settings.cache_clear()
    body = json.loads(FIXTURE.read_text(encoding="utf-8"))["responses"][0]

    response_counter = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal response_counter
        request_payload = json.loads(request.content)
        assert request_payload["registrationkey"] == "do-not-persist-this-key"
        response_counter += 1
        response_body = {**body, "responseTime": response_counter}
        return httpx.Response(200, request=request, json=response_body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await BLSAdapter(client).fetch(
            _provider(), [(_source(), _dataset())], mode="incremental"
        )
        repeated = await BLSAdapter(client).fetch(
            _provider(), [(_source(), _dataset())], mode="incremental"
        )

    serialized = results[0].raw_bytes + json.dumps(
        results[0].request_parameters, sort_keys=True
    ).encode()
    assert b"do-not-persist-this-key" not in serialized
    assert b"registrationkey" not in serialized
    assert results[0].raw_bytes == repeated[0].raw_bytes
    assert b"responseTime" not in results[0].raw_bytes
    assert all(item.vintage_at == results[0].captured_at for item in results[0].observations)
    get_settings.cache_clear()


async def test_worker_forwards_single_source_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    from macrolens_worker import runner

    captured: dict[str, object] = {}
    session = object()

    class SessionContext(AbstractAsyncContextManager[object]):
        async def __aenter__(self) -> object:
            return session

        async def __aexit__(self, *_args: object) -> None:
            return None

    async def fake_sync(_session: object, **kwargs: object) -> dict[str, str]:
        captured.update(kwargs)
        return {"status": "succeeded"}

    monkeypatch.setattr(runner, "SessionLocal", SessionContext)
    monkeypatch.setattr(runner, "sync_provider", fake_sync)
    job = SimpleNamespace(
        id="00000000-0000-0000-0000-000000000009",
        job_type="sync_provider",
        payload={
            "provider_code": "BLS_API_V2",
            "mode": "incremental",
            "source_series_ids": [42],
        },
    )

    assert await runner.execute_job(job) == {"status": "succeeded"}
    assert captured["provider_code"] == "BLS_API_V2"
    assert captured["source_series_ids"] == [42]


async def test_admin_identity_or_status_change_revokes_probe_binding() -> None:
    from macrolens_api.routers.admin import update_source_mapping
    from macrolens_api.schemas import SourceMappingUpdate

    mapping = SimpleNamespace(
        id=42,
        provider_series_id="CUSR0000SA0",
        source_locator={"expected_catalog_title": TITLE},
        mapping_status="verified",
        is_primary=True,
        notes=None,
        verified_by="reviewer@example.test",
        verified_at=datetime(2026, 1, 13, tzinfo=UTC),
        verification_job_id="probe-job",
        verification_fingerprint="a" * 64,
    )

    class FakeSession:
        async def get(self, _model: object, _key: object) -> object:
            return mapping

        async def commit(self) -> None:
            return None

    await update_source_mapping(  # type: ignore[arg-type]
        42,
        SourceMappingUpdate(provider_series_id="CUSR0000SA0-CHANGED"),
        FakeSession(),
        SimpleNamespace(email="admin@example.test"),
    )
    assert mapping.mapping_status == "needs_review"
    assert mapping.is_primary is False
    assert mapping.verification_job_id is None

    mapping.mapping_status = "verified"
    mapping.is_primary = True
    mapping.verification_job_id = "probe-job-2"
    mapping.verification_fingerprint = "b" * 64
    await update_source_mapping(  # type: ignore[arg-type]
        42,
        SourceMappingUpdate(mapping_status="disabled"),
        FakeSession(),
        SimpleNamespace(email="admin@example.test"),
    )
    assert mapping.mapping_status == "disabled"
    assert mapping.is_primary is False
    assert mapping.verification_job_id is None


async def test_consumed_mapping_probe_cannot_be_retried() -> None:
    from macrolens_api.errors import AppError
    from macrolens_api.routers.admin import retry_job

    job = SimpleNamespace(job_type="mapping_probe", result={"approval": {"id": 42}})

    class FakeSession:
        async def get(self, _model: object, _key: object) -> object:
            return job

    with pytest.raises(AppError) as error:
        await retry_job(  # type: ignore[arg-type]
            __import__("uuid").UUID("00000000-0000-0000-0000-000000000042"),
            FakeSession(),
            SimpleNamespace(email="admin@example.test"),
        )
    assert error.value.code == "mapping_probe_already_consumed"


async def test_probe_approval_atomically_demotes_old_primary() -> None:
    from macrolens_api.services.source_mapping_identity import source_mapping_fingerprint
    from macrolens_api.services.source_mappings import approve_mapping_from_probe

    mapping = SimpleNamespace(
        id=42,
        series_id="series-id",
        dataset_id=7,
        provider_series_id="CUSR0000SA0",
        source_locator={"expected_catalog_title": TITLE},
        mapping_type="direct",
        source_frequency="monthly",
        source_unit="index",
        source_seasonal_adjustment="seasonally_adjusted",
        mapping_status="needs_review",
        is_primary=False,
        verified_by=None,
        verified_at=None,
        verification_job_id=None,
        verification_fingerprint=None,
    )
    dataset = _dataset()
    provider = _provider()
    job = SimpleNamespace(
        id="probe-job",
        job_type="mapping_probe",
        status="succeeded",
        payload={"source_series_id": 42},
        result={
            "source_series_id": 42,
            "provider_code": "BLS_API_V2",
            "provider_series_id": "CUSR0000SA0",
            "http_reachable": True,
            "http_status": 200,
            "business_success": True,
            "identity_match": True,
            "authorization_available": True,
            "production_ready": True,
            "classification": "PASS",
            "response_sha256": "a" * 64,
            "mapping_fingerprint": source_mapping_fingerprint(
                mapping, dataset, provider
            ),
        },
    )

    class MappingResult:
        def one_or_none(self) -> tuple[object, object, object]:
            return mapping, dataset, provider

    class FakeSession:
        def __init__(self) -> None:
            self.update_executed = False
            self.committed = False
            self.execute_calls = 0

        async def scalar(self, _statement: object) -> object:
            return job

        async def execute(self, _statement: object) -> object:
            self.execute_calls += 1
            if self.execute_calls % 2 == 1:
                return MappingResult()
            self.update_executed = True
            return None

        async def commit(self) -> None:
            self.committed = True

    session = FakeSession()
    approved = await approve_mapping_from_probe(  # type: ignore[arg-type]
        session,
        source_series_id=42,
        probe_job_id="probe-job",
        verified_by="reviewer@example.test",
    )
    assert session.update_executed is True
    assert session.committed is True
    assert approved.mapping_status == "verified"
    assert approved.is_primary is True
    assert approved.verified_by == "reviewer@example.test"
    assert approved.verification_job_id == "probe-job"
    first_verified_at = approved.verified_at
    await approve_mapping_from_probe(  # type: ignore[arg-type]
        session,
        source_series_id=42,
        probe_job_id="probe-job",
        verified_by="reviewer@example.test",
    )
    assert approved.verified_at == first_verified_at
    assert session.execute_calls == 3

    mapping.provider_series_id = "CHANGED_AFTER_PROBE"
    with pytest.raises(RuntimeError, match="not approved"):
        await approve_mapping_from_probe(  # type: ignore[arg-type]
            FakeSession(),
            source_series_id=42,
            probe_job_id=__import__("uuid").UUID(
                "00000000-0000-0000-0000-000000000042"
            ),
            verified_by="reviewer@example.test",
        )


async def test_identical_raw_replay_does_not_create_another_vintage() -> None:
    from decimal import Decimal

    from macrolens_worker.providers.base import NormalizedObservation
    from macrolens_worker.tasks.sync import _merge_observation

    observation = NormalizedObservation(
        source_series_id=42,
        period_start=datetime(2025, 12, 1).date(),
        period_end=datetime(2025, 12, 31).date(),
        value=Decimal("324.054"),
        vintage_at=datetime(2026, 1, 14, 13, 30, tzinfo=UTC),
        source_updated_at=datetime(2026, 1, 14, 13, 30, tzinfo=UTC),
    )
    existing = SimpleNamespace(
        period_end=observation.period_end,
        value=observation.value,
        value_text=None,
        observation_status="normal",
        published_at=None,
        source_updated_at=datetime(2026, 1, 13, 13, 30, tzinfo=UTC),
        quality_flags=[],
    )

    class FakeSession:
        def __init__(self) -> None:
            self.scalar_calls = 0

        async def scalar(self, _statement: object) -> object:
            self.scalar_calls += 1
            return existing

    session = FakeSession()
    outcome = await _merge_observation(  # type: ignore[arg-type]
        session,
        observation,
        run_id="run-id",  # type: ignore[arg-type]
        raw_object_id="raw-id",  # type: ignore[arg-type]
        publication_batch_id="batch-id",  # type: ignore[arg-type]
    )
    assert outcome == "unchanged"
    assert session.scalar_calls == 1

    existing.observation_status = "revised"
    with pytest.raises(ValueError, match="different immutable observation payload"):
        await _merge_observation(  # type: ignore[arg-type]
            FakeSession(),
            observation,
            run_id="run-id",  # type: ignore[arg-type]
            raw_object_id="raw-id",  # type: ignore[arg-type]
            publication_batch_id="batch-id",  # type: ignore[arg-type]
        )


async def test_same_raw_payload_with_a_new_vintage_is_not_treated_as_exact_replay() -> None:
    from decimal import Decimal

    from macrolens_worker.providers.base import NormalizedObservation
    from macrolens_worker.tasks.sync import _merge_observation

    observation = NormalizedObservation(
        source_series_id=42,
        period_start=datetime(2025, 12, 1).date(),
        period_end=datetime(2025, 12, 31).date(),
        value=Decimal("324.054"),
        vintage_at=datetime(2026, 1, 15, 13, 30, tzinfo=UTC),
        source_updated_at=datetime(2026, 1, 15, 13, 30, tzinfo=UTC),
    )
    previous_vintage = SimpleNamespace(
        period_end=observation.period_end,
        value=observation.value,
        value_text=None,
        observation_status="normal",
        published_at=None,
        source_updated_at=datetime(2026, 1, 14, 13, 30, tzinfo=UTC),
        quality_flags=[],
        vintage_at=datetime(2026, 1, 14, 13, 30, tzinfo=UTC),
    )

    class FakeSession:
        def __init__(self) -> None:
            self.scalar_statements: list[object] = []
            self.added: list[object] = []
            self.executed: list[object] = []

        async def scalar(self, statement: object) -> object | None:
            self.scalar_statements.append(statement)
            if len(self.scalar_statements) == 1:
                replay_sql = str(statement)
                if "observation_vintage.vintage_at =" not in replay_sql:
                    return previous_vintage
            return None

        def add(self, value: object) -> None:
            self.added.append(value)

        async def execute(self, statement: object) -> None:
            self.executed.append(statement)

    session = FakeSession()
    outcome = await _merge_observation(  # type: ignore[arg-type]
        session,
        observation,
        run_id="run-id",  # type: ignore[arg-type]
        raw_object_id="raw-id",  # type: ignore[arg-type]
        publication_batch_id="batch-id",  # type: ignore[arg-type]
    )

    assert outcome == "inserted"
    assert len(session.scalar_statements) == 3
    assert "observation_vintage.vintage_at =" in str(session.scalar_statements[0])
    assert len(session.added) == 1
    assert session.added[0].vintage_at == observation.vintage_at
    assert len(session.executed) == 1


async def test_worker_offline_replay_validates_stored_raw_without_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hashlib import sha256
    from uuid import UUID

    from macrolens_worker.tasks import mappings

    raw_bytes = FIXTURE.read_bytes()
    raw_object = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000099"),
        provider_id=3,
        dataset_id=7,
        object_uri="s3://fixture-bucket/raw/bls/cpi.json",
        sha256=sha256(raw_bytes).hexdigest(),
        fetched_at=datetime(2026, 1, 13, 13, 30, tzinfo=UTC),
    )

    class FakeStorage:
        settings = SimpleNamespace(s3_bucket="fixture-bucket")

        async def get_bytes(self, key: str) -> bytes:
            assert key == "raw/bls/cpi.json"
            return raw_bytes

    class MappingRows:
        def __init__(self, rows: list[tuple[object, object, object]]) -> None:
            self.rows = rows

        def all(self) -> list[tuple[object, object, object]]:
            return self.rows

    class FakeSession:
        async def get(self, _model: object, _key: object) -> object:
            return raw_object

        async def execute(self, _statement: object) -> MappingRows:
            rows = [(_source(), _dataset(), _provider())] if raw_object.dataset_id == 7 else []
            return MappingRows(rows)

    monkeypatch.setattr(mappings, "ObjectStorage", FakeStorage)
    result = await mappings.replay_bls_raw(  # type: ignore[arg-type]
        FakeSession(),
        raw_object_id=raw_object.id,
        source_series_ids=[42],
    )
    assert result == {
        "status": "validated",
        "raw_object_id": str(raw_object.id),
        "raw_sha256": raw_object.sha256,
        "source_series_ids": [42],
        "observation_count": 2,
        "first_period": "2025-11-01",
        "last_period": "2025-12-01",
        "network_requests": 0,
    }
    raw_object.dataset_id = 8
    with pytest.raises(RuntimeError, match="scope"):
        await mappings.replay_bls_raw(  # type: ignore[arg-type]
            FakeSession(),
            raw_object_id=raw_object.id,
            source_series_ids=[42],
        )


def test_cpi_registry_and_schema_pin_identity_and_unique_primary() -> None:
    root = Path(__file__).resolve().parents[2]
    registry = json.loads(
        (root / "database/seed/source_registry.json").read_text(encoding="utf-8")
    )
    cpi = next(
        item for item in registry["indicators"] if item["canonical_code"] == "US.CPI.HEADLINE"
    )
    assert cpi["recommended_source"] == "BLS_API_V2"
    assert cpi["provider_series_id"] == "CUSR0000SA0"
    assert cpi["locator"]["expected_catalog"] == {
        "series_id": "CUSR0000SA0",
        "seasonality": "Seasonally Adjusted",
        "survey_abbreviation": "CU",
        "area": "U.S. city average",
        "item": "All items",
    }
    migration = (
        root / "backend/alembic/versions/0002_unique_primary_source.py"
    ).read_text(encoding="utf-8")
    assert "CREATE UNIQUE INDEX one_primary_source_per_series" in migration
    assert "WHERE is_primary" in migration
    assert "verification_job_id" in migration
    seed_source = (root / "backend/src/macrolens_api/cli.py").read_text(
        encoding="utf-8"
    )
    assert 'source_series.verified_by = "seed-registry"' not in seed_source
    assert "was_probe_approved" in seed_source


def test_internal_series_routes_cover_full_cpi_product_chain() -> None:
    from macrolens_api.routers.series import router
    from macrolens_api.schemas import ObservationPoint, RevisionItem

    paths = {route.path for route in router.routes}
    assert "/series/browser" in paths
    assert "/series/{series_id}" in paths
    assert "/series/{series_id}/observations" in paths
    assert "/series/{series_id}/revisions" in paths
    assert "/series/{series_id}/analytics" in paths
    assert "/series/{series_id}/export" in paths
    assert {
        "source_series_id",
        "run_id",
        "publication_batch_id",
        "raw_object_id",
    }.issubset(ObservationPoint.model_fields)
    from macrolens_api.schemas import BrowserObservation

    assert {
        "source_series_id",
        "run_id",
        "publication_batch_id",
        "raw_object_id",
    }.issubset(BrowserObservation.model_fields)
    from macrolens_worker import runner

    assert "replay_bls_raw" in __import__("inspect").getsource(runner.execute_job)
    assert {
        "first_run_id",
        "latest_run_id",
        "first_raw_object_id",
        "latest_raw_object_id",
    }.issubset(RevisionItem.model_fields)
