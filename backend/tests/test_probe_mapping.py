from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from macrolens_api.config import get_settings
from macrolens_api.services.source_mapping_identity import source_mapping_fingerprint
from macrolens_worker.tasks import mappings

FIXTURES = Path(__file__).parent / "fixtures/mapping_probes"
BLS_FIXTURE = Path(__file__).parent / "fixtures/bls/cpi_headline_2025.json"


class _RowResult:
    def __init__(self, row: tuple[object, object, object] | None) -> None:
        self.row = row

    def one_or_none(self) -> tuple[object, object, object] | None:
        return self.row


class _ReadOnlySession:
    def __init__(self, row: tuple[object, object, object] | None) -> None:
        self.row = row

    async def execute(self, _statement: object) -> _RowResult:
        return _RowResult(self.row)


def _source(
    provider_code: str,
) -> tuple[SimpleNamespace, SimpleNamespace, SimpleNamespace]:
    common = {
        "id": 73,
        "mapping_type": "direct",
        "source_unit": "index",
        "source_seasonal_adjustment": None,
    }
    if provider_code == "BLS_API_V2":
        source = SimpleNamespace(
            **common,
            provider_series_id="CUSR0000SA0",
            source_frequency="monthly",
            source_locator={
                "expected_catalog_title": (
                    "All items in U.S. city average, all urban consumers, seasonally adjusted"
                )
            },
        )
        dataset = SimpleNamespace(id=10, code="Public Data API")
    elif provider_code == "EIA_API_V2":
        source = SimpleNamespace(
            **common,
            provider_series_id="PET.RWTC.D",
            source_frequency="daily",
            source_locator={
                "route": "v2/seriesid/PET.RWTC.D",
                "expected_first_period": "1986-01-02",
                "min_observations_backfill": 100,
            },
        )
        dataset = SimpleNamespace(id=11, code="Petroleum")
    elif provider_code == "BEA_API":
        source = SimpleNamespace(
            **common,
            provider_series_id=None,
            source_frequency="monthly",
            source_locator={
                "table_name": "U20404",
                "frequency": "M",
                "series_code": "DHLCRA3",
                "line_number": "100",
                "line_description": "Health care services",
                "probe_year": "2025",
                "metric_name": "Price index",
                "cl_unit": "Index",
                "unit_mult": "0",
            },
        )
        dataset = SimpleNamespace(id=12, code="NIUnderlyingDetail")
    else:
        source = SimpleNamespace(
            **common,
            provider_series_id=None,
            source_frequency="monthly",
            source_locator={
                "path": "timeseries/eits/marts",
                "value_field": "cell_value",
                "time_field": "time",
                "required_variables": [
                    "cell_value",
                    "time",
                    "seasonally_adj",
                    "category_code",
                ],
                "dimensions": {
                    "seasonally_adj": "yes",
                    "category_code": "TOTAL",
                    "for": "us:*",
                },
                "probe_period": "2025-01",
            },
        )
        dataset = SimpleNamespace(id=13, code="marts")
    provider = SimpleNamespace(id=20, code=provider_code)
    return source, dataset, provider


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "provider_code",
    ["BLS_API_V2", "EIA_API_V2", "BEA_API", "CENSUS_EITS_API"],
)
async def test_probe_mapping_dispatches_all_supported_providers_and_binds_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
    provider_code: str,
) -> None:
    monkeypatch.setenv("BLS_API_KEY", "bls-secret")
    monkeypatch.setenv("EIA_API_KEY", "eia-secret")
    monkeypatch.setenv("BEA_API_KEY", "bea-secret")
    monkeypatch.setenv("CENSUS_API_KEY", "census-secret")
    get_settings.cache_clear()
    source, dataset, provider = _source(provider_code)
    bls_body = json.loads(BLS_FIXTURE.read_text())["responses"][0]
    eia_body = json.loads((FIXTURES / "eia_wti_pass.json").read_text())
    eia_body["response"]["data"][0]["series"] = "RWTC"
    response_by_provider = {
        "EIA_API_V2": json.dumps(eia_body, separators=(",", ":")).encode(),
        "BEA_API": (FIXTURES / "bea_pce_pass.json").read_bytes(),
        "CENSUS_EITS_API": (FIXTURES / "census_retail_pass.json").read_bytes(),
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(200, request=request, json=bls_body)
        return httpx.Response(200, request=request, content=response_by_provider[provider_code])

    real_async_client = httpx.AsyncClient

    def client_factory(**_kwargs: object) -> httpx.AsyncClient:
        return real_async_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(mappings.httpx, "AsyncClient", client_factory)
    result = await mappings.probe_mapping(
        _ReadOnlySession((source, dataset, provider)),  # type: ignore[arg-type]
        source_series_id=source.id,
    )

    assert result["provider_code"] == provider_code
    assert result["source_series_id"] == source.id
    assert result["provider_series_id"] == source.provider_series_id
    assert result["classification"] == "PASS"
    assert result["production_ready"] is True
    assert result["mapping_fingerprint"] == source_mapping_fingerprint(source, dataset, provider)
    assert isinstance(result["evidence"], dict)
    assert result["issues"] == []
    assert "secret" not in str(result)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_probe_mapping_fails_closed_for_unknown_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source, dataset, provider = _source("UNKNOWN_PROVIDER")

    def forbidden_client(**_kwargs: object) -> httpx.AsyncClient:
        raise AssertionError("unknown provider must fail before HTTP")

    monkeypatch.setattr(mappings.httpx, "AsyncClient", forbidden_client)
    with pytest.raises(RuntimeError, match="not implemented for provider UNKNOWN_PROVIDER"):
        await mappings.probe_mapping(
            _ReadOnlySession((source, dataset, provider)),  # type: ignore[arg-type]
            source_series_id=source.id,
        )
