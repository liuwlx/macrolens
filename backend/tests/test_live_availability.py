from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from macrolens_api.errors import AppError
from macrolens_api.schemas import ContributionResult, LicenseInfo
from macrolens_api.services import data_browser
from macrolens_api.services import series as series_service
from macrolens_api.services.data_browser import BrowserCandidate, BrowserFilters, SourceBinding
from macrolens_api.services.transforms import Point


def _candidate() -> BrowserCandidate:
    series_id = uuid4()
    series = SimpleNamespace(
        id=series_id,
        canonical_code="US.EMPTY",
        name_zh="空序列",
        name_en="Empty series",
        theme="activity",
        frequency="monthly",
        unit_code="index",
        unit_label_zh="指数",
        default_transform="level",
        decimal_places=2,
        seasonal_adjustment="sa",
    )
    source = SimpleNamespace(
        id=7,
        series_id=series_id,
        provider_series_id="EMPTY",
        source_locator={},
    )
    dataset = SimpleNamespace(id=8, code="EMPTY", provider_id=9)
    provider = SimpleNamespace(
        id=9,
        code="OFFICIAL",
        name="Official",
        attribution_text="Official source",
        license_class="public",
        redistribution_ok=True,
    )
    candidate = BrowserCandidate(series=series)  # type: ignore[arg-type]
    candidate.sources[source.id] = SourceBinding(source, dataset, provider)  # type: ignore[arg-type]
    return candidate


def _catalog_candidate(
    *,
    mapping_status: str,
    provider_code: str,
    verified: bool,
) -> BrowserCandidate:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None
    binding.source.mapping_status = mapping_status
    binding.source.is_primary = verified
    binding.provider.code = provider_code
    candidate.catalog_sources[binding.source.id] = binding
    if not verified:
        candidate.sources.clear()
    return candidate


def _license() -> LicenseInfo:
    return LicenseInfo(
        display_allowed=True,
        download_allowed=True,
        api_redistribution_allowed=True,
        ai_context_allowed=True,
        attribution_required=True,
        attribution_text="Official source",
    )


@pytest.mark.parametrize("availability", ["not_ingested", "not_available_as_of"])
async def test_live_browser_returns_empty_items_with_explicit_availability(
    monkeypatch: pytest.MonkeyPatch,
    availability: str,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None

    async def candidates(_session: object) -> list[BrowserCandidate]:
        return [candidate]

    async def licenses(_session: object, _bindings: object) -> dict[int, LicenseInfo]:
        return {binding.source.id: _license()}

    async def points(_session: object, _ids: object, **_kwargs: object) -> dict[int, list[object]]:
        return {}

    async def availability_by_source(
        _session: object,
        _ids: object,
        *,
        data_as_of: datetime,
    ) -> dict[int, str]:
        assert data_as_of == datetime(2020, 1, 1, tzinfo=UTC)
        return {binding.source.id: availability}

    monkeypatch.setattr(data_browser, "_load_candidates", candidates)
    monkeypatch.setattr(data_browser, "_license_map", licenses)
    monkeypatch.setattr(data_browser, "_points_by_source", points)
    monkeypatch.setattr(
        data_browser,
        "_lifetime_availability_by_source",
        availability_by_source,
        raising=False,
    )

    response = await data_browser.series_browser(
        object(),  # type: ignore[arg-type]
        filters=BrowserFilters(),
        sort="taxonomy",
        order="asc",
        limit=20,
        offset=0,
        data_as_of=datetime(2020, 1, 1, tzinfo=UTC),
        published_from=None,
        published_to=None,
    )

    assert response.items[0].current is None
    assert response.items[0].availability == availability
    assert response.data_mode == "live"


async def test_live_browser_marks_verified_visible_points_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None
    observed_at = datetime(2020, 1, 2, tzinfo=UTC)

    async def candidates(_session: object) -> list[BrowserCandidate]:
        return [candidate]

    async def licenses(_session: object, _bindings: object) -> dict[int, LicenseInfo]:
        return {binding.source.id: _license()}

    async def points(_session: object, _ids: object, **_kwargs: object) -> dict[int, list[Point]]:
        return {
            binding.source.id: [
                Point(
                    period_start=date(2020, 1, 1),
                    period_end=date(2020, 1, 31),
                    value=Decimal("100"),
                    value_text=None,
                    status="normal",
                    published_at=observed_at,
                    vintage_at=observed_at,
                )
            ]
        }

    monkeypatch.setattr(data_browser, "_load_candidates", candidates)
    monkeypatch.setattr(data_browser, "_license_map", licenses)
    monkeypatch.setattr(data_browser, "_points_by_source", points)

    response = await data_browser.series_browser(
        object(),  # type: ignore[arg-type]
        filters=BrowserFilters(),
        sort="taxonomy",
        order="asc",
        limit=20,
        offset=0,
        data_as_of=datetime(2020, 1, 3, tzinfo=UTC),
        published_from=None,
        published_to=None,
    )

    assert response.items[0].availability == "available"
    assert response.items[0].current is not None


async def test_live_browser_keeps_all_null_points_data_capabilities_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None
    observed_at = datetime(2020, 1, 2, tzinfo=UTC)

    async def candidates(_session: object) -> list[BrowserCandidate]:
        return [candidate]

    async def licenses(_session: object, _bindings: object) -> dict[int, LicenseInfo]:
        return {binding.source.id: _license()}

    async def points(_session: object, _ids: object, **_kwargs: object) -> dict[int, list[Point]]:
        return {
            binding.source.id: [
                Point(
                    period_start=date(2020, 1, 1),
                    period_end=date(2020, 1, 31),
                    value=None,
                    value_text="not published",
                    status="missing",
                    published_at=observed_at,
                    vintage_at=observed_at,
                )
            ]
        }

    async def availability_by_source(
        _session: object,
        ids: set[int],
        *,
        data_as_of: datetime,
    ) -> dict[int, str]:
        assert ids == {binding.source.id}
        assert data_as_of == datetime(2020, 1, 3, tzinfo=UTC)
        return {binding.source.id: "not_ingested"}

    monkeypatch.setattr(data_browser, "_load_candidates", candidates)
    monkeypatch.setattr(data_browser, "_license_map", licenses)
    monkeypatch.setattr(data_browser, "_points_by_source", points)
    monkeypatch.setattr(
        data_browser,
        "_lifetime_availability_by_source",
        availability_by_source,
    )

    response = await data_browser.series_browser(
        object(),  # type: ignore[arg-type]
        filters=BrowserFilters(),
        sort="taxonomy",
        order="asc",
        limit=20,
        offset=0,
        data_as_of=datetime(2020, 1, 3, tzinfo=UTC),
        published_from=None,
        published_to=None,
    )

    assert response.items[0].availability == "not_ingested"
    assert response.items[0].current is None


@pytest.mark.parametrize(
    ("mapping_status", "provider_code", "verified", "expected"),
    [
        ("needs_review", "BEA_API", False, "pending_mapping"),
        ("license_required", "LICENSED_VENDOR", False, "pending_license"),
        ("verified", "FRED_API", True, "pending_credentials"),
    ],
)
async def test_live_browser_keeps_catalog_only_series_visible_with_exact_readiness(
    monkeypatch: pytest.MonkeyPatch,
    mapping_status: str,
    provider_code: str,
    verified: bool,
    expected: str,
) -> None:
    candidate = _catalog_candidate(
        mapping_status=mapping_status,
        provider_code=provider_code,
        verified=verified,
    )
    binding = candidate.binding

    async def candidates(_session: object) -> list[BrowserCandidate]:
        return [candidate]

    async def licenses(_session: object, _bindings: object) -> dict[int, LicenseInfo]:
        return {binding.source.id: _license()} if binding is not None else {}

    async def points(_session: object, _ids: object, **_kwargs: object) -> dict[int, list[object]]:
        return {}

    async def availability_by_source(
        _session: object,
        ids: set[int],
        *,
        data_as_of: datetime,
    ) -> dict[int, str]:
        assert data_as_of == datetime(2020, 1, 1, tzinfo=UTC)
        return {source_id: "not_ingested" for source_id in ids}

    monkeypatch.setattr(data_browser, "_load_candidates", candidates)
    monkeypatch.setattr(data_browser, "_license_map", licenses)
    monkeypatch.setattr(data_browser, "_points_by_source", points)
    monkeypatch.setattr(
        data_browser,
        "_lifetime_availability_by_source",
        availability_by_source,
    )
    monkeypatch.setattr(
        data_browser,
        "_provider_credentials_ready",
        lambda _provider_code: False,
        raising=False,
    )

    response = await data_browser.series_browser(
        object(),  # type: ignore[arg-type]
        filters=BrowserFilters(provider=provider_code),
        sort="taxonomy",
        order="asc",
        limit=20,
        offset=0,
        data_as_of=datetime(2020, 1, 1, tzinfo=UTC),
        published_from=None,
        published_to=None,
    )

    assert response.pagination.total == 1
    assert response.items[0].availability == expected
    assert response.items[0].current is None
    assert response.items[0].series.provider is not None
    assert response.items[0].series.provider.code == provider_code
    assert response.facets.provider[0].value == provider_code


@pytest.mark.parametrize("operation", ["csv", "analytics"])
async def test_live_never_ingested_single_series_returns_200_shape(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None

    async def candidates(_session: object, *, series_id: object) -> list[BrowserCandidate]:
        assert series_id == candidate.series.id
        return [candidate]

    async def licenses(_session: object, _bindings: object) -> dict[int, LicenseInfo]:
        return {binding.source.id: _license()}

    async def points(_session: object, _ids: object, **_kwargs: object) -> dict[int, list[object]]:
        return {}

    async def earliest(_session: object, _ids: object) -> dict[int, datetime]:
        return {}

    async def contributions(*_args: object, **_kwargs: object) -> ContributionResult:
        return ContributionResult(available=False, reason_code="not_ingested")

    async def next_release(*_args: object, **_kwargs: object) -> None:
        return None

    monkeypatch.setattr(data_browser, "_load_candidates", candidates)
    monkeypatch.setattr(data_browser, "_license_map", licenses)
    monkeypatch.setattr(data_browser, "_points_by_source", points)
    monkeypatch.setattr(data_browser, "_earliest_vintage_by_source", earliest, raising=False)
    monkeypatch.setattr(data_browser, "_contributions", contributions)
    monkeypatch.setattr(data_browser, "_next_release", next_release)

    cutoff = datetime(2020, 1, 1, tzinfo=UTC)
    if operation == "csv":
        content = await data_browser.series_csv(
            object(),  # type: ignore[arg-type]
            series_id=candidate.series.id,
            start=None,
            end=None,
            transform="level",
            data_as_of=cutoff,
        )
        header = content.decode("utf-8-sig").splitlines()[0]
        assert header.startswith(
            "series_id,canonical_code,name_zh,period_start,period_end,value,status,"
            "published_at,vintage_at,data_as_of,data_mode,transform,unit,provider,attribution"
        )
        assert header.endswith(
            ",source_series_id,run_id,publication_batch_id,raw_object_id"
        )
    else:
        response = await data_browser.series_analytics(
            object(),  # type: ignore[arg-type]
            series_id=candidate.series.id,
            start=None,
            end=None,
            transform="level",
            data_as_of=cutoff,
        )
        assert response.statistics.count == 0
        assert response.data_mode == "live"


@pytest.mark.parametrize("operation", ["csv", "analytics"])
async def test_live_single_series_rejects_cutoff_before_first_lifetime_vintage(
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None

    async def candidates(_session: object, *, series_id: object) -> list[BrowserCandidate]:
        return [candidate]

    async def licenses(_session: object, _bindings: object) -> dict[int, LicenseInfo]:
        return {binding.source.id: _license()}

    async def points(_session: object, _ids: object, **_kwargs: object) -> dict[int, list[object]]:
        return {}

    async def earliest(_session: object, _ids: object) -> dict[int, datetime]:
        return {binding.source.id: datetime(2021, 1, 1, tzinfo=UTC)}

    monkeypatch.setattr(data_browser, "_load_candidates", candidates)
    monkeypatch.setattr(data_browser, "_license_map", licenses)
    monkeypatch.setattr(data_browser, "_points_by_source", points)
    monkeypatch.setattr(data_browser, "_earliest_vintage_by_source", earliest, raising=False)

    cutoff = datetime(2020, 1, 1, tzinfo=UTC)
    with pytest.raises(AppError) as captured:
        if operation == "csv":
            await data_browser.series_csv(
                object(),  # type: ignore[arg-type]
                series_id=candidate.series.id,
                start=None,
                end=None,
                transform="level",
                data_as_of=cutoff,
            )
        else:
            await data_browser.series_analytics(
                object(),  # type: ignore[arg-type]
                series_id=candidate.series.id,
                start=None,
                end=None,
                transform="level",
                data_as_of=cutoff,
            )
    assert captured.value.status_code == 409
    assert captured.value.code == "snapshot_unavailable"


async def test_live_observations_never_ingested_returns_empty_200_shape(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None

    class FakeSession:
        async def get(self, _model: object, _id: object) -> object:
            return candidate.series

    async def primary(*_args: object) -> tuple[object, object, object]:
        return binding.source, binding.dataset, binding.provider

    async def rows(*_args: object, **_kwargs: object) -> list[object]:
        return []

    async def earliest(*_args: object) -> None:
        return None

    async def license_for(*_args: object) -> LicenseInfo:
        return _license()

    monkeypatch.setattr(series_service, "get_primary_source", primary)
    monkeypatch.setattr(series_service, "get_license", license_for)
    monkeypatch.setattr(series_service, "_query_vintage_points", rows)
    monkeypatch.setattr(series_service, "_earliest_vintage_at", earliest, raising=False)

    response = await series_service.get_observations(
        FakeSession(),  # type: ignore[arg-type]
        series_id=candidate.series.id,
        start=None,
        end=None,
        transform="level",
        data_as_of=datetime(2020, 1, 1, tzinfo=UTC),
        historical_cutoff=True,
    )
    assert response.data == []
    assert response.meta.data_mode == "live"


async def test_live_observations_rejects_cutoff_before_first_lifetime_vintage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _candidate()
    binding = candidate.binding
    assert binding is not None

    class FakeSession:
        async def get(self, _model: object, _id: object) -> object:
            return candidate.series

    async def primary(*_args: object) -> tuple[object, object, object]:
        return binding.source, binding.dataset, binding.provider

    async def rows(*_args: object, **_kwargs: object) -> list[object]:
        return []

    async def earliest(*_args: object) -> datetime:
        return datetime(2021, 1, 1, tzinfo=UTC)

    async def license_for(*_args: object) -> LicenseInfo:
        return _license()

    monkeypatch.setattr(series_service, "get_primary_source", primary)
    monkeypatch.setattr(series_service, "get_license", license_for)
    monkeypatch.setattr(series_service, "_query_vintage_points", rows)
    monkeypatch.setattr(series_service, "_earliest_vintage_at", earliest, raising=False)

    with pytest.raises(AppError) as captured:
        await series_service.get_observations(
            FakeSession(),  # type: ignore[arg-type]
            series_id=candidate.series.id,
            start=None,
            end=None,
            transform="level",
            data_as_of=datetime(2020, 1, 1, tzinfo=UTC),
            historical_cutoff=True,
        )
    assert captured.value.status_code == 409
    assert captured.value.code == "snapshot_unavailable"
