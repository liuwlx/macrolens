from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from macrolens_api.errors import AppError
from macrolens_api.schemas import AIRunCreate, BrowserPagination, LicenseInfo, SeriesBrowserResponse
from macrolens_api.services import ai_context, data_browser
from macrolens_api.services.data_browser import BrowserCandidate, SourceBinding
from macrolens_api.services.transforms import Point


def _license(*, display: bool = True, download: bool = True, ai: bool = True) -> LicenseInfo:
    return LicenseInfo(
        display_allowed=display,
        download_allowed=download,
        api_redistribution_allowed=download,
        ai_context_allowed=ai,
        attribution_required=True,
        attribution_text="Official source",
    )


def _candidate() -> BrowserCandidate:
    series_id = uuid4()
    series = SimpleNamespace(
        id=series_id,
        canonical_code="US.TEST",
        name_zh="测试指标",
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
        id=3,
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
