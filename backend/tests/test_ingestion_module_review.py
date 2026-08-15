from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from lxml import html

from macrolens_api.config import get_settings
from macrolens_worker.providers.base import ProviderDataError


def dataset(dataset_id: int = 1, code: str = "dataset") -> SimpleNamespace:
    return SimpleNamespace(id=dataset_id, code=code)


def source(
    source_id: int = 1,
    *,
    external_id: str | None = "TEST",
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


async def test_fred_rejects_registry_metadata_history_boundary_drift(monkeypatch) -> None:
    from macrolens_worker.providers.fred import FREDAdapter

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/fred/series")
        return httpx.Response(
            200,
            request=request,
            json={
                "seriess": [
                    {
                        "id": "TEST",
                        "frequency_short": "M",
                        "observation_start": "2020-02-01",
                        "title": "Test",
                    }
                ]
            },
        )

    mapped = source(
        external_id="TEST",
        locator={"expected_first_period": "2020-01-01"},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="history boundary mismatch"):
            await FREDAdapter(client).fetch(
                SimpleNamespace(code="FRED_API"), [(mapped, dataset())], mode="backfill"
            )
    get_settings.cache_clear()


async def test_fred_rejects_repeated_page_even_when_count_matches(monkeypatch) -> None:
    from macrolens_worker.providers.fred import FREDAdapter

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    get_settings.cache_clear()
    page = [
        {
            "date": "2020-01-01",
            "value": "1",
            "realtime_start": "2020-02-01",
            "realtime_end": "9999-12-31",
        },
        {
            "date": "2020-02-01",
            "value": "2",
            "realtime_start": "2020-03-01",
            "realtime_end": "9999-12-31",
        },
    ]

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
        return httpx.Response(200, request=request, json={"count": 4, "observations": page})

    mapped = source(
        external_id="TEST",
        locator={"expected_first_period": "2020-01-01"},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = FREDAdapter(client)
        adapter.page_size = 2
        with pytest.raises(ProviderDataError, match="repeated observation"):
            await adapter.fetch(
                SimpleNamespace(code="FRED_API"), [(mapped, dataset())], mode="backfill"
            )
    get_settings.cache_clear()


async def test_eia_collects_every_page_and_declared_row(monkeypatch) -> None:
    from macrolens_worker.providers.eia import EIAAdapter

    monkeypatch.setenv("EIA_API_KEY", "test-key")
    get_settings.cache_clear()
    offsets: list[int] = []
    rows = [
        {"period": "1986-01-02", "value": "25.56"},
        {"period": "1986-01-03", "value": "26.00"},
        {"period": "1986-01-06", "value": "26.53"},
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        length = int(request.url.params["length"])
        offsets.append(offset)
        return httpx.Response(
            200,
            request=request,
            json={"response": {"total": "3", "data": rows[offset : offset + length]}},
        )

    mapped = source(
        frequency="daily",
        external_id="PET.RWTC.D",
        locator={
            "route": "v2/seriesid/PET.RWTC.D",
            "value_field": "value",
            "data_fields": ["value"],
            "expected_first_period": "1986-01-02",
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = EIAAdapter(client)
        adapter.page_size = 2
        result = await adapter.fetch(
            SimpleNamespace(code="EIA_API_V2"), [(mapped, dataset())], mode="backfill"
        )
    assert offsets == [0, 2]
    assert [row.period_start for row in result[0].observations] == [
        date(1986, 1, 2),
        date(1986, 1, 3),
        date(1986, 1, 6),
    ]
    get_settings.cache_clear()


async def test_nyfed_sparse_rrp_allows_empty_historical_windows() -> None:
    from macrolens_worker.providers.nyfed import NYFedAdapter

    current_year = date.today().year
    previous_year = current_year - 1

    async def handler(request: httpx.Request) -> httpx.Response:
        start_year = int(str(request.url.params["startDate"])[:4])
        operations = []
        if start_year == current_year:
            operations = [
                {
                    "operationDate": f"{current_year}-01-02",
                    "totalAmtAccepted": "12.5",
                }
            ]
        return httpx.Response(200, request=request, json={"repo": {"operations": operations}})

    mapped = source(
        external_id="RRP_TOTAL_ACCEPTED",
        frequency="daily",
        locator={
            "route": "rp/results/search.json",
            "start_date": f"{previous_year}-01-01",
            "field": "totalAmtAccepted",
            "aggregation": "sum",
            "allow_empty_windows": True,
            "params": {
                "operationTypes": "reverserepo",
                "securityType": "tsy",
                "term": "Overnight",
            },
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await NYFedAdapter(client).fetch(
            SimpleNamespace(code="NYFED_MARKETS_API"), [(mapped, dataset())], mode="backfill"
        )
    assert len(result[0].observations) == 1
    assert str(result[0].observations[0].value) == "12.5"


async def test_census_rejects_duplicate_period_after_dimensions_are_pinned(monkeypatch) -> None:
    from macrolens_worker.providers.census import CensusEITSAdapter

    monkeypatch.setenv("CENSUS_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json=[
                ["cell_value", "time", "seasonally_adj"],
                ["100", "2026-01", "yes"],
                ["100", "2026-01", "yes"],
            ],
        )

    mapped = source(
        locator={
            "path": "timeseries/eits/test",
            "value_field": "cell_value",
            "dimensions": {"seasonally_adj": "yes"},
        }
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="duplicate period"):
            await CensusEITSAdapter(client).fetch(
                SimpleNamespace(code="CENSUS_EITS_API"), [(mapped, dataset())], mode="backfill"
            )
    get_settings.cache_clear()


async def test_dol_rejects_duplicate_period_in_snapshot(monkeypatch) -> None:
    from macrolens_worker.providers.dol import DOLOpenDataAdapter

    monkeypatch.setenv("DOL_CLAIMS_URL", "https://example.dol.gov/claims")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={
                "total": 2,
                "data": [
                    {"week_ending": "2026-07-11", "claims": "100"},
                    {"week_ending": "2026-07-11", "claims": "100"},
                ],
            },
        )

    mapped = source(
        frequency="weekly",
        locator={
            "date_field": "week_ending",
            "value_field": "claims",
            "complete_snapshot": True,
        },
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="duplicate period"):
            await DOLOpenDataAdapter(client).fetch(
                SimpleNamespace(code="DOL_OPEN_DATA_API"), [(mapped, dataset())], mode="backfill"
            )
    get_settings.cache_clear()


async def test_bea_rejects_conflicting_description_for_same_row_identity(monkeypatch) -> None:
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
                                "DataValue": "100",
                            },
                            {
                                "SeriesCode": "AAA",
                                "LineNumber": "1",
                                "LineDescription": "Hospital services",
                                "TimePeriod": "2026M02",
                                "DataValue": "101",
                            },
                        ]
                    }
                }
            },
        )

    mapped = source(
        frequency="monthly",
        locator={"table_name": "U20404", "frequency": "M", "line_number": "1"},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="conflicting descriptions"):
            await BEAAdapter(client).fetch(
                SimpleNamespace(code="BEA_API"),
                [(mapped, dataset(code="NIUnderlyingDetail"))],
                mode="backfill",
            )
    get_settings.cache_clear()


async def test_bls_requires_catalog_metadata_when_identity_title_is_pinned(monkeypatch) -> None:
    from macrolens_worker.providers.bls import BLSAdapter

    monkeypatch.setenv("BLS_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        return httpx.Response(
            200,
            request=request,
            json={
                "status": "REQUEST_SUCCEEDED",
                "Results": {
                    "series": [
                        {
                            "seriesID": payload["seriesid"][0],
                            "data": [
                                {
                                    "year": "2026",
                                    "period": "M01",
                                    "value": "100",
                                    "footnotes": [],
                                }
                            ],
                        }
                    ]
                },
            },
        )

    mapped = source(
        external_id="SERIES",
        locator={"start_year": 2026, "expected_catalog_title": "Pinned title"},
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="catalog metadata missing"):
            await BLSAdapter(client).fetch(
                SimpleNamespace(code="BLS_API_V2"), [(mapped, dataset())], mode="incremental"
            )
    get_settings.cache_clear()


def test_fomc_calendar_rejects_partially_parseable_meeting_rows() -> None:
    from macrolens_worker.tasks.fomc import _parse_calendar_rows

    document = html.fromstring(
        """
        <div class='panel'>
          <h3>2026 FOMC Meetings</h3>
          <div class='fomc-meeting'>
            <span class='month'>January</span><span class='date'>27-28</span>
          </div>
          <div class='fomc-meeting'>
            <span class='month'>NotAMonth</span><span class='date'>17-18</span>
          </div>
        </div>
        """
    )
    with pytest.raises(RuntimeError, match="partially parseable"):
        _parse_calendar_rows(document)


def test_registry_pins_every_enabled_history_boundary() -> None:
    root = Path(__file__).resolve().parents[2]
    registry = json.loads((root / "database/seed/source_registry.json").read_text())
    enabled = [item for item in registry["indicators"] if item["mapping_status"] == "READY"]
    assert len(enabled) == 33
    for item in enabled:
        locator = item.get("locator") or {}
        assert locator.get("expected_first_period") or locator.get("start_year"), item[
            "canonical_code"
        ]
    by_code = {item["canonical_code"]: item for item in enabled}
    assert by_code["US.BANK.CREDIT"]["provider_series_id"] == "TOTBKCR"
    assert by_code["US.WTI"]["locator"]["expected_first_period"] == "1986-01-02"
    assert by_code["US.SLOOS"]["locator"]["expected_first_period"] == "1990-04-01"


def test_live_ingestion_audit_workflow_covers_every_registered_adapter_and_full_history() -> None:
    from macrolens_worker.tasks.sync import ADAPTERS

    workflow = Path(".github/workflows/live-ingestion-audit.yml").read_text()
    for provider_code in ADAPTERS:
        assert f"--provider {provider_code}" in workflow
    assert "43 6 1 * *" in workflow
    assert "value=backfill" in workflow


def test_collection_module_review_lists_every_registered_adapter() -> None:
    from macrolens_worker.tasks.sync import ADAPTERS

    report = json.loads(Path("DATA_COLLECTION_MODULE_REVIEW.json").read_text())
    reviewed = {entry.get("code") for entry in report["modules"]}
    assert set(ADAPTERS).issubset(reviewed)
    assert report["guarantee_model"] == "fail_closed_no_partial_publish"
