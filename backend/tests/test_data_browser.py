from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from macrolens_api.errors import AppError, request_validation_error_handler
from macrolens_api.schemas import AIRunCreate, BrowserPagination, LicenseInfo, SeriesBrowserResponse
from macrolens_api.services import ai_context, ai_runtime, data_browser, jobs, licenses
from macrolens_api.services import series as series_service
from macrolens_api.services.data_browser import BrowserCandidate, BrowserFilters, SourceBinding
from macrolens_api.services.transforms import Point

ROOT = Path(__file__).resolve().parents[2]


def _license(*, display: bool = True, download: bool = True, ai: bool = True) -> LicenseInfo:
    return LicenseInfo(
        display_allowed=display,
        download_allowed=download,
        api_redistribution_allowed=download,
        ai_context_allowed=ai,
        attribution_required=True,
        attribution_text="Official source",
    )


def _candidate(*, source_id: int = 3, name: str = "测试指标") -> BrowserCandidate:
    series_id = uuid4()
    series = SimpleNamespace(
        id=series_id,
        canonical_code="US.TEST",
        name_zh=name,
        name_en="Test series",
        theme="activity",
        frequency="monthly",
        unit_code="index",
        unit_label_zh="指数",
        default_transform="level",
        decimal_places=2,
        seasonal_adjustment="sa",
    )
    provider = SimpleNamespace(
        id=1,
        code="OFFICIAL",
        name="Official",
        attribution_text="Official source",
        license_class="reviewed",
        redistribution_ok=True,
    )
    dataset = SimpleNamespace(id=2, code="TEST", provider_id=1)
    source = SimpleNamespace(
        id=source_id,
        series_id=series_id,
        provider_series_id="TEST",
        source_locator={},
    )
    candidate = BrowserCandidate(series=series)  # type: ignore[arg-type]
    candidate.sources[source.id] = SourceBinding(source, dataset, provider)  # type: ignore[arg-type]
    return candidate


def test_ai_run_create_accepts_a_frozen_data_as_of() -> None:
    cutoff = datetime(2026, 8, 1, tzinfo=UTC)
    payload = AIRunCreate(
        prompt="Analyze this official series",
        data_as_of=cutoff,
        contexts=[{"context_type": "series", "context_id": uuid4()}],
    )
    assert payload.data_as_of == cutoff


def test_csv_cells_neutralize_formulas_and_record_controls() -> None:
    assert data_browser._csv_safe("=1+1") == "'=1+1"
    assert data_browser._csv_safe("+SUM(A1:A2)") == "'+SUM(A1:A2)"
    assert data_browser._csv_safe("\t@command\nnext") == "' @command next"
    assert data_browser._csv_safe("ordinary") == "ordinary"


def test_browser_export_rejects_more_than_ten_thousand_rows_before_writing() -> None:
    response = SeriesBrowserResponse.model_construct(
        items=[],
        facets=None,
        pagination=BrowserPagination(total=10_001, limit=10_000, offset=0),
        data_as_of=datetime(2026, 8, 1, tzinfo=UTC),
    )
    with pytest.raises(AppError, match="export_limit_exceeded") as captured:
        data_browser.browser_csv(response)
    assert captured.value.status_code == 413


async def test_license_resolution_fails_closed_without_one_effective_policy() -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None

    class ScalarRows:
        def __init__(self, rows: list[object]) -> None:
            self.rows = rows

        def all(self) -> list[object]:
            return self.rows

    class FakeSession:
        def __init__(self, rows: list[object]) -> None:
            self.rows = rows

        async def scalars(self, _statement: object) -> ScalarRows:
            return ScalarRows(self.rows)

    missing = await data_browser._license_map(FakeSession([]), [binding])  # type: ignore[arg-type]
    assert not missing[binding.source.id].display_allowed
    assert not missing[binding.source.id].ai_context_allowed

    policy = SimpleNamespace(
        provider_id=binding.provider.id,
        dataset_id=binding.dataset.id,
        display_allowed=True,
        download_allowed=True,
        api_redistribution_allowed=True,
        ai_context_allowed=True,
        attribution_required=True,
        attribution_text="Official source",
    )
    conflict = await data_browser._license_map(  # type: ignore[arg-type]
        FakeSession([policy, policy]),
        [binding],
    )
    assert not conflict[binding.source.id].display_allowed


async def test_series_ai_context_reauthorizes_and_uses_requested_vintage_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None
    cutoff = datetime(2026, 7, 31, 16, 0, tzinfo=UTC)
    captured: dict[str, datetime] = {}

    async def candidates(_session: object, *, series_id: object) -> list[BrowserCandidate]:
        assert series_id == candidate.series.id
        return [candidate]

    async def licenses(_session: object, _bindings: object) -> dict[int, LicenseInfo]:
        return {binding.source.id: _license()}

    async def points(
        _session: object,
        _source_ids: object,
        *,
        data_as_of: datetime,
        max_points: int,
    ) -> dict[int, list[Point]]:
        captured["cutoff"] = data_as_of
        assert max_points == 36
        return {
            binding.source.id: [
                Point(
                    period_start=date(2026, 6, 1),
                    period_end=date(2026, 6, 30),
                    value=Decimal("101.5"),
                    status="normal",
                    published_at=cutoff,
                    vintage_at=cutoff,
                    value_text=None,
                )
            ]
        }

    monkeypatch.setattr(ai_context, "_load_candidates", candidates)
    monkeypatch.setattr(ai_context, "_license_map", licenses)
    monkeypatch.setattr(ai_context, "_points_by_source", points)
    workspace_id = uuid4()
    snapshot = await ai_context.snapshot_context(
        object(),  # type: ignore[arg-type]
        "series",
        candidate.series.id,
        workspace_id=workspace_id,
        user_id=uuid4(),
        data_as_of=cutoff,
    )
    assert captured["cutoff"] == cutoff
    assert snapshot["data_as_of"] == cutoff.isoformat()
    assert snapshot["workspace_id"] == str(workspace_id)


async def test_contributions_fail_closed_without_definition_version_binding() -> None:
    result = await data_browser._contributions(  # type: ignore[arg-type]
        object(),
        _candidate(),
        [],
        start=None,
        end=None,
        data_as_of=datetime(2026, 8, 1, tzinfo=UTC),
    )
    assert not result.available
    assert result.reason_code == "contribution_version_binding_unavailable"


def test_numeric_detail_routes_require_user_workspace_and_share_data_as_of() -> None:
    source = (ROOT / "backend/src/macrolens_api/routers/series.py").read_text(encoding="utf-8")
    for endpoint in ("series_observations", "series_revisions"):
        function = source.split(f"async def {endpoint}(", 1)[1].split(") ->", 1)[0]
        assert "_user: CurrentUser" in function
        assert "_workspace: CurrentWorkspace" in function
        assert "data_as_of: datetime | None" in function
    service = (ROOT / "backend/src/macrolens_api/services/series.py").read_text(encoding="utf-8")
    observation_impl = service.split("async def get_observations(", 1)[1].split(
        "async def get_revisions(", 1
    )[0]
    assert "ObservationLatest" not in observation_impl
    assert "ObservationVintage.vintage_at <= data_as_of" in service


def test_browser_and_export_default_to_seeded_taxonomy_tree() -> None:
    source = (ROOT / "backend/src/macrolens_api/routers/series.py").read_text(encoding="utf-8")
    assert source.count('tree_code: str = Query(default="macro-default"') == 2
    sdk = (ROOT / "packages/sdk-typescript/src/index.ts").read_text(encoding="utf-8")
    assert sdk.count('tree_code: "macro-default"') == 2


async def test_observations_use_the_exact_vintage_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None
    cutoff = datetime(2026, 7, 1, tzinfo=UTC)
    captured: dict[str, str] = {}

    class FakeSession:
        async def get(self, _model: object, _id: object) -> object:
            return candidate.series

    async def primary(_session: object, _series_id: object) -> tuple[object, object, object]:
        return binding.source, binding.dataset, binding.provider

    async def license_for(_session: object, _provider: object, _dataset: object) -> LicenseInfo:
        return _license()

    async def vintage_points(
        _session: object,
        _source_id: int,
        _start: date | None,
        _end: date | None,
        vintage: str,
    ) -> list[object]:
        captured["vintage"] = vintage
        return [
            SimpleNamespace(
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
                value=Decimal("100"),
                value_text=None,
                observation_status="normal",
                published_at=cutoff,
                vintage_at=cutoff,
            )
        ]

    async def summary(_session: object, _series: object, *args: object) -> object:
        return data_browser._summary(candidate, None)

    monkeypatch.setattr(series_service, "get_primary_source", primary)
    monkeypatch.setattr(series_service, "get_license", license_for)
    monkeypatch.setattr(series_service, "_query_vintage_points", vintage_points)
    monkeypatch.setattr(series_service, "build_series_summary", summary)
    result = await series_service.get_observations(
        FakeSession(),  # type: ignore[arg-type]
        series_id=candidate.series.id,
        start=None,
        end=None,
        transform="level",
        data_as_of=cutoff,
    )
    assert captured["vintage"] == cutoff.isoformat()
    assert result.meta.data_as_of == cutoff


async def test_browser_loads_histories_only_for_the_selected_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidates = [
        _candidate(source_id=index, name=name)
        for index, name in enumerate(["A", "B", "C", "D", "E"], start=1)
    ]
    loaded: set[int] = set()

    async def load_candidates(_session: object) -> list[BrowserCandidate]:
        return candidates

    async def licenses(_session: object, bindings: list[SourceBinding]) -> dict[int, LicenseInfo]:
        return {binding.source.id: _license() for binding in bindings}

    async def points(
        _session: object,
        source_ids: set[int],
        *,
        data_as_of: datetime,
        max_points: int = 420,
    ) -> dict[int, list[Point]]:
        del data_as_of
        assert max_points == 420
        loaded.update(source_ids)
        return {
            source_id: [
                Point(
                    period_start=date(2026, 6, 1),
                    period_end=date(2026, 6, 30),
                    value=Decimal(source_id),
                    status="normal",
                    published_at=datetime(2026, 7, 1, tzinfo=UTC),
                    vintage_at=datetime(2026, 7, 1, tzinfo=UTC),
                )
            ]
            for source_id in source_ids
        }

    monkeypatch.setattr(data_browser, "_load_candidates", load_candidates)
    monkeypatch.setattr(data_browser, "_license_map", licenses)
    monkeypatch.setattr(data_browser, "_points_by_source", points)
    result = await data_browser.series_browser(
        object(),  # type: ignore[arg-type]
        filters=BrowserFilters(),
        sort="taxonomy",
        order="asc",
        limit=2,
        offset=1,
        data_as_of=None,
        published_from=None,
        published_to=None,
    )
    assert result.pagination.total == 5
    assert [item.series.name_zh for item in result.items] == ["B", "C"]
    assert loaded == {2, 3}


async def test_historical_non_series_ai_context_fails_closed() -> None:
    cutoff = datetime(2026, 1, 1, tzinfo=UTC)
    with pytest.raises(AppError) as captured:
        await ai_context.snapshot_context(
            object(),  # type: ignore[arg-type]
            "document",
            uuid4(),
            data_as_of=cutoff,
            historical_cutoff=True,
        )
    assert captured.value.code == "historical_context_unavailable"
    assert captured.value.extra == {
        "context_type": "document",
        "data_as_of": cutoff.isoformat(),
    }


async def test_request_validation_errors_use_problem_details() -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/series/browser",
            "headers": [],
            "query_string": b"limit=0",
            "scheme": "http",
            "server": ("test", 80),
            "client": ("test", 1234),
        }
    )
    error = RequestValidationError(
        [
            {
                "type": "greater_than_equal",
                "loc": ("query", "limit"),
                "msg": "Input should be greater than or equal to 1",
                "input": 0,
            }
        ]
    )
    response = await request_validation_error_handler(request, error)
    body = json.loads(response.body)
    assert response.status_code == 422
    assert body["code"] == "request_validation_error"
    assert body["type"].endswith("/request_validation_error")
    assert body["errors"][0]["location"] == ["query", "limit"]
    main_source = (ROOT / "backend/src/macrolens_api/main.py").read_text(encoding="utf-8")
    assert "app.add_exception_handler(\n    RequestValidationError" in main_source


async def test_job_reservation_replays_an_existing_idempotency_key() -> None:
    existing_id = uuid4()
    existing = SimpleNamespace(id=existing_id, payload={"ai_run_id": str(uuid4())})

    class FakeSession:
        calls = 0

        async def scalar(self, _statement: object) -> object | None:
            self.calls += 1
            return None if self.calls == 1 else existing_id

        async def get(self, _model: object, object_id: object) -> object | None:
            return existing if object_id == existing_id else None

    job, created = await jobs.reserve_job(
        FakeSession(),  # type: ignore[arg-type]
        job_type="run_ai_analysis",
        payload={"ai_run_id": str(uuid4())},
        idempotency_key="ai-run-request:test",
    )
    assert not created
    assert job is existing


def test_ai_run_route_requires_and_reuses_idempotency_key() -> None:
    source = (ROOT / "backend/src/macrolens_api/routers/ai.py").read_text(encoding="utf-8")
    assert 'Header(alias="Idempotency-Key"' in source
    assert "await reserve_job(" in source
    assert '"idempotency_key_reused"' in source


async def test_strict_provider_license_denies_missing_or_ambiguous_policy() -> None:
    provider = SimpleNamespace(redistribution_ok=True, attribution_text="Official source")

    class PolicyRows:
        def __init__(self, rows: list[object]) -> None:
            self.rows = rows

        def all(self) -> list[object]:
            return self.rows

    class FakeSession:
        def __init__(self, policies: list[object]) -> None:
            self.policies = policies

        async def get(self, _model: object, _object_id: object) -> object:
            return provider

        async def scalars(self, _statement: object) -> PolicyRows:
            return PolicyRows(self.policies)

    missing = await licenses.get_strict_license_for_provider(
        FakeSession([]),  # type: ignore[arg-type]
        provider_id=1,
    )
    assert not missing.ai_context_allowed
    assert not missing.api_redistribution_allowed

    policy = SimpleNamespace(
        dataset_id=None,
        display_allowed=True,
        download_allowed=True,
        api_redistribution_allowed=True,
        ai_context_allowed=True,
        attribution_required=True,
        attribution_text="Policy attribution",
    )
    ambiguous = await licenses.get_strict_license_for_provider(
        FakeSession([policy, policy]),  # type: ignore[arg-type]
        provider_id=1,
    )
    assert not ambiguous.ai_context_allowed
    assert not ambiguous.api_redistribution_allowed


def test_ai_runtime_requires_key_and_both_models_before_reservation() -> None:
    assert not ai_runtime.ai_runtime_configured(
        SimpleNamespace(
            openai_api_key=None,
            openai_model="gpt-main",
            openai_deep_research_model="gpt-deep",
        )  # type: ignore[arg-type]
    )
    assert not ai_runtime.ai_runtime_configured(
        SimpleNamespace(
            openai_api_key="secret",
            openai_model=" ",
            openai_deep_research_model="gpt-deep",
        )  # type: ignore[arg-type]
    )
    assert ai_runtime.ai_runtime_configured(
        SimpleNamespace(
            openai_api_key="secret",
            openai_model="gpt-main",
            openai_deep_research_model="gpt-deep",
        )  # type: ignore[arg-type]
    )
    source = (ROOT / "backend/src/macrolens_api/routers/ai.py").read_text(encoding="utf-8")
    configuration_check = source.index("if not ai_runtime_configured(settings):")
    reservation = source.index("await reserve_job(")
    assert configuration_check < reservation
