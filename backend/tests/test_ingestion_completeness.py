from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from macrolens_api.config import get_settings
from macrolens_worker.data_readiness import audit_source_registry
from macrolens_worker.providers.base import (
    NormalizedObservation,
    ProviderDataError,
    deduplicate_observations,
    parse_period_code,
)
from macrolens_worker.tasks.ingestion_quality import validate_ingestion_completeness

REPO_ROOT = Path(__file__).resolve().parents[2]


def _dataset(dataset_id: int, code: str = "dataset") -> SimpleNamespace:
    return SimpleNamespace(id=dataset_id, code=code)


def _source(
    source_id: int,
    *,
    external_id: str | None = None,
    frequency: str = "monthly",
    locator: dict | None = None,
    title: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=source_id,
        provider_series_id=external_id,
        source_frequency=frequency,
        source_locator=locator or {},
        source_title=title,
    )


def test_bls_period_codes_cover_quarterly_semiannual_and_annual() -> None:
    assert parse_period_code(2026, "Q01", "quarterly") == date(2026, 1, 1)
    assert parse_period_code(2026, "Q4", "quarterly") == date(2026, 10, 1)
    assert parse_period_code(2026, "S02", "semiannual") == date(2026, 7, 1)
    assert parse_period_code(2026, "M13", "annual") == date(2026, 1, 1)
    assert parse_period_code(2026, "M13", "monthly") is None


async def test_bls_adapter_collects_quarterly_eci(monkeypatch) -> None:
    from macrolens_worker.providers.bls import BLSAdapter

    monkeypatch.setenv("BLS_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["registrationkey"] == "test-key"
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "REQUEST_SUCCEEDED",
                "Results": {
                    "series": [
                        {
                            "seriesID": "ECI",
                            "data": [
                                {
                                    "year": "2026",
                                    "period": "Q02",
                                    "value": "168.2",
                                    "latest": "true",
                                    "footnotes": [],
                                },
                                {
                                    "year": "2026",
                                    "period": "Q01",
                                    "value": "166.9",
                                    "latest": "false",
                                    "footnotes": [],
                                },
                            ],
                        }
                    ]
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BLSAdapter(client).fetch(
            SimpleNamespace(code="BLS_API_V2"),
            [(_source(1, external_id="ECI", frequency="quarterly"), _dataset(1))],
            mode="incremental",
        )
    assert [row.period_start for row in result[0].observations] == [
        date(2026, 1, 1),
        date(2026, 4, 1),
    ]
    assert result[0].observations[-1].period_end == date(2026, 6, 30)
    get_settings.cache_clear()


async def test_fred_adapter_paginates_current_history(monkeypatch) -> None:
    from macrolens_worker.providers.fred import FREDAdapter

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    get_settings.cache_clear()
    offsets: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fred/series"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "seriess": [
                        {
                            "id": "TEST",
                            "frequency_short": "M",
                            "observation_start": "2026-01-01",
                            "title": "Test",
                        }
                    ]
                },
            )
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        all_rows = [
            {
                "date": "2026-01-01",
                "value": "1",
                "realtime_start": "2026-02-01",
                "realtime_end": "9999-12-31",
            },
            {
                "date": "2026-02-01",
                "value": "2",
                "realtime_start": "2026-03-01",
                "realtime_end": "9999-12-31",
            },
            {
                "date": "2026-03-01",
                "value": "3",
                "realtime_start": "2026-04-01",
                "realtime_end": "9999-12-31",
            },
        ]
        limit = int(request.url.params["limit"])
        return httpx.Response(
            200,
            request=request,
            json={"count": 3, "observations": all_rows[offset : offset + limit]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = FREDAdapter(client)
        adapter.page_size = 2
        result = await adapter.fetch(
            SimpleNamespace(code="FRED_API"),
            [(_source(2, external_id="TEST"), _dataset(2))],
            mode="incremental",
        )
    assert offsets == [0, 2]
    assert [str(item.value) for item in result[0].observations] == ["1", "2", "3"]
    get_settings.cache_clear()


async def test_fred_adapter_can_backfill_alfred_vintages(monkeypatch) -> None:
    from macrolens_worker.providers.fred import FREDAdapter

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fred/series"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "seriess": [
                        {
                            "id": "TEST",
                            "frequency_short": "M",
                            "observation_start": "2026-01-01",
                            "title": "Test",
                        }
                    ]
                },
            )
        if request.url.path.endswith("/vintagedates"):
            return httpx.Response(
                200,
                request=request,
                json={"count": 2, "vintage_dates": ["2026-02-01", "2026-03-01"]},
            )
        assert request.url.params["output_type"] == "2"
        return httpx.Response(
            200,
            request=request,
            json={
                "count": 2,
                "observations": [
                    {
                        "date": "2026-01-01",
                        "value": "100",
                        "realtime_start": "2026-02-01",
                        "realtime_end": "2026-02-28",
                    },
                    {
                        "date": "2026-01-01",
                        "value": "101",
                        "realtime_start": "2026-03-01",
                        "realtime_end": "9999-12-31",
                    },
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await FREDAdapter(client).fetch(
            SimpleNamespace(code="FRED_API"),
            [(_source(3, external_id="TEST"), _dataset(3))],
            mode="vintage_backfill",
        )
    assert len(result[0].observations) == 2
    assert [str(item.value) for item in result[0].observations] == ["100", "101"]
    assert [item.vintage_at.date() for item in result[0].observations] == [
        date(2026, 2, 1),
        date(2026, 3, 1),
    ]
    get_settings.cache_clear()


async def test_bea_adapter_resolves_exact_line_description(monkeypatch) -> None:
    from macrolens_worker.providers.bea import BEAAdapter

    monkeypatch.setenv("BEA_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "BEAAPI": {
                    "Results": {
                        "Data": [
                            {
                                "SeriesCode": "AAA",
                                "LineNumber": "1",
                                "LineDescription": "Health care services",
                                "TimePeriod": "2026M01",
                                "DataValue": "110",
                            },
                            {
                                "SeriesCode": "BBB",
                                "LineNumber": "2",
                                "LineDescription": "Hospital services",
                                "TimePeriod": "2026M01",
                                "DataValue": "120",
                            },
                        ]
                    }
                }
            },
        )

    source = _source(
        4,
        frequency="monthly",
        locator={"table_name": "U20404", "frequency": "M", "line_match": "Health care services"},
        title="Health Care Services",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BEAAdapter(client).fetch(
            SimpleNamespace(code="BEA_API"),
            [(source, _dataset(4, "NIUnderlyingDetail"))],
            mode="incremental",
        )
    assert str(result[0].observations[0].value) == "110"
    raw = json.loads(result[0].raw_bytes)
    assert raw["resolved_identities"]["4"]["series_code"] == "AAA"
    get_settings.cache_clear()


async def test_eia_rejects_repeated_pagination_page(monkeypatch) -> None:
    from macrolens_worker.providers.eia import EIAAdapter

    monkeypatch.setenv("EIA_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "response": {
                    "total": 4,
                    "data": [
                        {"period": "2026-07-01", "value": "70"},
                        {"period": "2026-07-02", "value": "71"},
                    ],
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = EIAAdapter(client)
        adapter.page_size = 2
        with pytest.raises(ProviderDataError, match="repeated a page"):
            await adapter.fetch(
                SimpleNamespace(code="EIA_API_V2"),
                [
                    (
                        _source(5, frequency="daily", locator={"route": "v2/seriesid/TEST"}),
                        _dataset(5),
                    )
                ],
                mode="backfill",
            )
    get_settings.cache_clear()


async def test_nyfed_rrp_aggregates_multiple_operations_per_day() -> None:
    from macrolens_worker.providers.nyfed import NYFedAdapter

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/api/rp/results/search.json")
        assert request.url.params["operationTypes"] == "reverserepo"
        assert request.url.params["securityType"] == "tsy"
        assert request.url.params["term"] == "Overnight"
        return httpx.Response(
            200,
            request=request,
            json={
                "repo": {
                    "operations": [
                        {"operationDate": "2026-07-31", "totalAmtAccepted": "10"},
                        {"operationDate": "2026-07-31", "totalAmtAccepted": "15"},
                    ]
                }
            },
        )

    source = _source(
        6,
        external_id="RRP_TOTAL_ACCEPTED",
        frequency="daily",
        locator={
            "route": "rp/results/search.json",
            "field": "totalAmtAccepted",
            "aggregation": "sum",
            "params": {
                "operationTypes": "reverserepo",
                "securityType": "tsy",
                "term": "Overnight",
            },
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await NYFedAdapter(client).fetch(
            SimpleNamespace(code="NYFED_MARKETS_API"), [(source, _dataset(6))], mode="incremental"
        )
    assert str(result[0].observations[0].value) == "25"


def test_treasury_null_fields_are_not_observations() -> None:
    from macrolens_worker.providers.treasury import TreasuryAdapter

    raw = (
        b'<?xml version="1.0"?>'
        b'<feed xmlns:d="x" xmlns:m="y"><entry><content><m:properties>'
        b"<d:NEW_DATE>2026-07-31T00:00:00</d:NEW_DATE>"
        b'<d:BC_2YEAR m:null="true" />'
        b"</m:properties></content></entry></feed>"
    )
    source = _source(7, external_id="2Y_PAR_NOMINAL", frequency="daily")
    assert TreasuryAdapter(client=None)._parse(raw, [(source, _dataset(7))]) == []  # type: ignore[arg-type]


def test_completeness_gate_blocks_missing_gap_and_stale_data() -> None:
    source = _source(
        8,
        frequency="monthly",
        locator={
            "min_observations": 3,
            "require_contiguous": True,
            "max_staleness_days": 30,
        },
    )
    vintage = datetime(2026, 8, 1, tzinfo=UTC)
    observations = [
        NormalizedObservation(
            8,
            date(2026, 1, 1),
            date(2026, 1, 31),
            __import__("decimal").Decimal("1"),
            vintage_at=vintage,
        ),
        NormalizedObservation(
            8,
            date(2026, 3, 1),
            date(2026, 3, 31),
            __import__("decimal").Decimal("2"),
            vintage_at=vintage,
        ),
    ]
    issues, metrics = validate_ingestion_completeness(
        [(source, _dataset(8))],
        observations,
        mode="incremental",
        now=datetime(2026, 8, 2, tzinfo=UTC),
    )
    codes = {issue.code for issue in issues}
    assert {"minimum_history", "history_gap", "stale_latest_period"} <= codes
    assert metrics["coverage_ratio"] == 1.0


def test_duplicate_snapshot_conflicts_are_rejected() -> None:
    from decimal import Decimal

    vintage = datetime(2026, 8, 1, tzinfo=UTC)
    first = NormalizedObservation(
        9, date(2026, 1, 1), date(2026, 1, 31), Decimal("1"), vintage_at=vintage
    )
    second = NormalizedObservation(
        9, date(2026, 1, 1), date(2026, 1, 31), Decimal("2"), vintage_at=vintage
    )
    with pytest.raises(ProviderDataError, match="Conflicting duplicate"):
        deduplicate_observations([first, second])


def test_source_registry_readiness_is_explicit_and_no_unmapped_series_is_enabled(
    monkeypatch,
) -> None:
    for key in ("BEA_API_KEY", "BLS_API_KEY", "FRED_API_KEY", "EIA_API_KEY", "CENSUS_API_KEY"):
        monkeypatch.setenv(key, "test-key")
    monkeypatch.setenv("DOL_CLAIMS_URL", "https://example.dol.gov/claims")
    get_settings.cache_clear()
    report = audit_source_registry(
        REPO_ROOT / "database/seed/source_registry.json",
        check_credentials=True,
    )
    assert report["indicator_count"] == 61
    assert report["ready_count"] == 31
    assert report["blocked_count"] == 30
    assert report["enabled_indicator_count"] == 31
    assert report["enabled_ready_count"] == 31
    assert report["enabled_blocked_count"] == 0
    assert report["all_enabled_ready"]
    assert not report["all_production_ready"]
    by_code = {item["canonical_code"]: item for item in report["indicators"]}
    assert by_code["US.PCE.MEDICAL"]["status"] == "blocked_mapping"
    assert by_code["US.MICHIGAN.1Y"]["status"] in {"blocked_license", "blocked_adapter"}
    assert by_code["US.SP500"]["status"] == "blocked_license"
    get_settings.cache_clear()


def test_completeness_rejects_missing_latest_values_but_allows_derived_bootstrap() -> None:
    from decimal import Decimal

    now = datetime(2026, 8, 2, tzinfo=UTC)
    source = _source(
        20,
        frequency="monthly",
        locator={
            "min_observations_incremental": 2,
            "max_staleness_days": 90,
            "require_contiguous": True,
        },
    )
    rows = [
        NormalizedObservation(
            20, date(2026, 5, 1), date(2026, 5, 31), Decimal("1"), vintage_at=now
        ),
        NormalizedObservation(20, date(2026, 6, 1), date(2026, 6, 30), None, vintage_at=now),
    ]
    issues, _metrics = validate_ingestion_completeness(
        [(source, _dataset(20))], rows, mode="incremental", now=now
    )
    assert "missing_observation_value" in {issue.code for issue in issues}

    derived = _source(
        21,
        frequency="monthly",
        locator={
            "transform": "period_difference",
            "periods": 1,
            "min_observations_incremental": 2,
            "max_staleness_days": 90,
            "require_contiguous": True,
        },
    )
    derived_rows = [
        NormalizedObservation(21, date(2026, 5, 1), date(2026, 5, 31), None, vintage_at=now),
        NormalizedObservation(
            21, date(2026, 6, 1), date(2026, 6, 30), Decimal("2"), vintage_at=now
        ),
        NormalizedObservation(
            21, date(2026, 7, 1), date(2026, 7, 31), Decimal("3"), vintage_at=now
        ),
    ]
    derived_issues, _metrics = validate_ingestion_completeness(
        [(derived, _dataset(21))], derived_rows, mode="incremental", now=now
    )
    assert "missing_observation_value" not in {issue.code for issue in derived_issues}


async def test_fred_metadata_identity_and_frequency_are_enforced(monkeypatch) -> None:
    from macrolens_worker.providers.fred import FREDAdapter

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fred/series"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "seriess": [
                        {
                            "id": "TEST",
                            "frequency_short": "Q",
                            "observation_start": "2000-01-01",
                            "title": "Wrong frequency test",
                        }
                    ]
                },
            )
        raise AssertionError("observations must not be requested after metadata mismatch")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="frequency mismatch"):
            await FREDAdapter(client).fetch(
                SimpleNamespace(code="FRED_API"),
                [(_source(22, external_id="TEST", frequency="monthly"), _dataset(22))],
                mode="incremental",
            )
    get_settings.cache_clear()


async def test_treasury_rejects_empty_expected_year() -> None:
    from macrolens_worker.providers.treasury import TreasuryAdapter

    empty_feed = b"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom"></feed>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=empty_feed)

    source = _source(
        23,
        external_id="2Y_PAR_NOMINAL",
        frequency="daily",
        locator={"start_year": 2026},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="returned no observations"):
            await TreasuryAdapter(client).fetch(
                SimpleNamespace(code="US_TREASURY_XML"),
                [(source, _dataset(23))],
                mode="backfill",
            )


def test_backfill_completeness_rejects_truncated_verified_start() -> None:
    from decimal import Decimal

    source = _source(
        30,
        frequency="monthly",
        locator={
            "expected_first_period": "2020-01-01",
            "min_observations_backfill": 1,
            "max_staleness_days": 5000,
            "require_contiguous": True,
        },
    )
    vintage = datetime(2026, 8, 2, tzinfo=UTC)
    observations = [
        NormalizedObservation(
            30,
            date(2020, 2, 1),
            date(2020, 2, 29),
            Decimal("1"),
            vintage_at=vintage,
        )
    ]
    issues, _metrics = validate_ingestion_completeness(
        [(source, _dataset(30))],
        observations,
        mode="backfill",
        now=vintage,
    )
    assert "history_start_mismatch" in {issue.code for issue in issues}


async def test_bls_rejects_missing_requested_series(monkeypatch) -> None:
    from macrolens_worker.providers.bls import BLSAdapter

    monkeypatch.setenv("BLS_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        first = payload["seriesid"][0]
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "REQUEST_SUCCEEDED",
                "Results": {
                    "series": [
                        {
                            "seriesID": first,
                            "catalog": {"series_title": "first"},
                            "data": [
                                {
                                    "year": "2026",
                                    "period": "M01",
                                    "value": "100",
                                    "latest": "true",
                                    "footnotes": [],
                                }
                            ],
                        }
                    ]
                },
            },
        )

    sources = [
        _source(31, external_id="SERIES_A", locator={"start_year": 2025}),
        _source(32, external_id="SERIES_B", locator={"start_year": 2025}),
    ]
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="coverage mismatch"):
            await BLSAdapter(client).fetch(
                SimpleNamespace(code="BLS_API_V2"),
                [(source, _dataset(31)) for source in sources],
                mode="incremental",
            )
    get_settings.cache_clear()


async def test_census_rejects_short_matrix_rows(monkeypatch) -> None:
    from macrolens_worker.providers.census import CensusEITSAdapter

    monkeypatch.setenv("CENSUS_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=[
                ["cell_value", "time", "seasonally_adj"],
                ["100", "2026-01"],
            ],
        )

    source = _source(
        33,
        locator={
            "path": "timeseries/eits/test",
            "value_field": "cell_value",
            "dimensions": {"seasonally_adj": "yes"},
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="cells"):
            await CensusEITSAdapter(client).fetch(
                SimpleNamespace(code="CENSUS_EITS_API"),
                [(source, _dataset(33))],
                mode="incremental",
            )
    get_settings.cache_clear()


async def test_dol_rejects_incomplete_declared_total(monkeypatch) -> None:
    from macrolens_worker.providers.dol import DOLOpenDataAdapter

    monkeypatch.setenv("DOL_CLAIMS_URL", "https://example.dol.gov/claims")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("offset", "0"))
        rows = (
            [
                {"week_ending": "2026-07-04", "claims": "100"},
                {"week_ending": "2026-07-11", "claims": "101"},
            ]
            if offset == 0
            else []
        )
        return httpx.Response(
            200,
            request=request,
            json={"total": 3, "data": rows},
        )

    source = _source(
        34,
        frequency="weekly",
        locator={
            "date_field": "week_ending",
            "value_field": "claims",
            "pagination": {"enabled": True, "page_size": 2},
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="incomplete"):
            await DOLOpenDataAdapter(client).fetch(
                SimpleNamespace(code="DOL_OPEN_DATA_API"),
                [(source, _dataset(34))],
                mode="backfill",
            )
    get_settings.cache_clear()


async def test_eia_rejects_duplicate_period_even_when_values_match(monkeypatch) -> None:
    from macrolens_worker.providers.eia import EIAAdapter

    monkeypatch.setenv("EIA_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "response": {
                    "total": 2,
                    "data": [
                        {"period": "2026-07-01", "value": "70"},
                        {"period": "2026-07-01", "value": "70"},
                    ],
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="more than one row"):
            await EIAAdapter(client).fetch(
                SimpleNamespace(code="EIA_API_V2"),
                [
                    (
                        _source(
                            35,
                            frequency="daily",
                            locator={"route": "v2/seriesid/TEST"},
                        ),
                        _dataset(35),
                    )
                ],
                mode="backfill",
            )
    get_settings.cache_clear()


async def test_fred_rejects_incomplete_vintage_date_pagination(monkeypatch) -> None:
    from macrolens_worker.providers.fred import FREDAdapter

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fred/series"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "seriess": [
                        {
                            "id": "TEST",
                            "frequency_short": "M",
                            "observation_start": "2026-01-01",
                            "title": "Test",
                        }
                    ]
                },
            )
        if request.url.path.endswith("/vintagedates"):
            offset = int(request.url.params.get("offset", "0"))
            return httpx.Response(
                200,
                request=request,
                json={
                    "count": 2,
                    "vintage_dates": ["2026-02-01"] if offset == 0 else [],
                },
            )
        raise AssertionError(request.url)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="vintage pagination incomplete"):
            await FREDAdapter(client).fetch(
                SimpleNamespace(code="FRED_API"),
                [(_source(36, external_id="TEST"), _dataset(36))],
                mode="vintage_backfill",
            )
    get_settings.cache_clear()


def test_parameterized_ics_properties_are_available_by_base_name() -> None:
    from macrolens_worker.tasks.release_calendar import parse_ics

    events = parse_ics(
        "BEGIN:VCALENDAR\r\n"
        "BEGIN:VEVENT\r\n"
        "SUMMARY;LANGUAGE=en-US:Consumer Price Index\\, United States\r\n"
        "DTSTART;TZID=America/New_York:20260812T083000\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    assert events[0]["SUMMARY"] == "Consumer Price Index, United States"
    assert events[0]["DTSTART"] == "20260812T083000"


def test_observation_merge_decision_preserves_older_and_unchanged_vintages() -> None:
    from decimal import Decimal
    from types import SimpleNamespace

    from macrolens_worker.tasks.sync import decide_observation_merge

    latest = SimpleNamespace(
        value=Decimal("101"),
        value_text=None,
        vintage_at=datetime(2026, 3, 1, tzinfo=UTC),
        observation_status="revised",
    )
    older = NormalizedObservation(
        source_series_id=77,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        value=Decimal("100"),
        vintage_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    older_decision = decide_observation_merge(older, latest)
    assert older_decision.outcome == "unchanged"
    assert older_decision.update_latest is False

    same_value_newer = NormalizedObservation(
        source_series_id=77,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        value=Decimal("101"),
        vintage_at=datetime(2026, 4, 1, tzinfo=UTC),
    )
    same_decision = decide_observation_merge(same_value_newer, latest)
    assert same_decision.outcome == "unchanged"
    assert same_decision.update_latest is True
    assert same_decision.latest_status == "revised"


def test_observation_merge_decision_marks_newer_changed_value_as_revision() -> None:
    from decimal import Decimal
    from types import SimpleNamespace

    from macrolens_worker.tasks.sync import decide_observation_merge

    latest = SimpleNamespace(
        value=Decimal("100"),
        value_text=None,
        vintage_at=datetime(2026, 2, 1, tzinfo=UTC),
        observation_status="normal",
    )
    incoming = NormalizedObservation(
        source_series_id=77,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        value=Decimal("101"),
        vintage_at=datetime(2026, 3, 1, tzinfo=UTC),
    )
    decision = decide_observation_merge(incoming, latest)
    assert decision.outcome == "revised"
    assert decision.update_latest is True
    assert decision.latest_status == "revised"
    assert decision.vintage_status == "revised"


def test_observation_merge_decision_rejects_same_vintage_conflict() -> None:
    from decimal import Decimal
    from types import SimpleNamespace

    from macrolens_worker.tasks.sync import decide_observation_merge

    latest = SimpleNamespace(
        value=Decimal("100"),
        value_text=None,
        vintage_at=datetime(2026, 2, 1, tzinfo=UTC),
        observation_status="normal",
    )
    incoming = NormalizedObservation(
        source_series_id=77,
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        value=Decimal("999"),
        vintage_at=datetime(2026, 2, 1, tzinfo=UTC),
    )
    with pytest.raises(ValueError, match="same vintage"):
        decide_observation_merge(incoming, latest)


async def test_fred_backfill_rejects_history_truncated_after_metadata_start(monkeypatch) -> None:
    from macrolens_worker.providers.fred import FREDAdapter

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/fred/series"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "seriess": [
                        {
                            "id": "TEST",
                            "frequency_short": "M",
                            "observation_start": "2020-01-01",
                            "title": "Test",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            request=request,
            json={
                "count": 2,
                "observations": [
                    {
                        "date": "2020-02-01",
                        "value": "2",
                        "realtime_start": "2020-03-01",
                        "realtime_end": "9999-12-31",
                    },
                    {
                        "date": "2020-03-01",
                        "value": "3",
                        "realtime_start": "2020-04-01",
                        "realtime_end": "9999-12-31",
                    },
                ],
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="expected metadata start"):
            await FREDAdapter(client).fetch(
                SimpleNamespace(code="FRED_API"),
                [(_source(88, external_id="TEST"), _dataset(88))],
                mode="backfill",
            )
    get_settings.cache_clear()


def test_live_audit_summary_applies_same_completeness_gate() -> None:
    from datetime import timedelta
    from decimal import Decimal

    from macrolens_worker.live_audit import summarize_live_fetch
    from macrolens_worker.providers.base import ProviderFetchResult

    today = date.today()
    source = _source(
        901,
        external_id="LIVE",
        frequency="daily",
        locator={
            "min_observations_incremental": 2,
            "max_staleness_days": 14,
            "require_contiguous": False,
        },
    )
    dataset = _dataset(901, "live")
    now = datetime.now(UTC)
    result = ProviderFetchResult(
        provider=SimpleNamespace(code="TEST"),
        dataset=dataset,
        request_url="https://example.test",
        request_parameters={},
        content_type="application/json",
        raw_bytes=b"{}",
        observations=[
            NormalizedObservation(
                901,
                today - timedelta(days=1),
                today - timedelta(days=1),
                Decimal("1"),
                vintage_at=now,
            ),
            NormalizedObservation(901, today, today, Decimal("2"), vintage_at=now),
        ],
    )
    report = summarize_live_fetch("TEST", [(source, dataset)], [result], mode="incremental")
    assert report["status"] == "passed"
    assert report["series"]["901"]["observation_count"] == 2


def test_live_audit_summary_fails_partial_source_coverage() -> None:
    from macrolens_worker.live_audit import summarize_live_fetch
    from macrolens_worker.providers.base import ProviderFetchResult

    source = _source(902, external_id="MISSING", locator={"min_observations_incremental": 1})
    dataset = _dataset(902, "live")
    result = ProviderFetchResult(
        provider=SimpleNamespace(code="TEST"),
        dataset=dataset,
        request_url="https://example.test",
        request_parameters={},
        content_type="application/json",
        raw_bytes=b"{}",
        observations=[],
    )
    report = summarize_live_fetch("TEST", [(source, dataset)], [result], mode="incremental")
    assert report["status"] == "failed"
    assert any(issue["code"] == "mapped_series_missing" for issue in report["issues"])
