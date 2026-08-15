from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from macrolens_api.config import get_settings
from macrolens_worker.providers.eia import EIAAdapter

FIXTURES = Path(__file__).parent / "fixtures/mapping_probes"


def _provider(code: str) -> SimpleNamespace:
    return SimpleNamespace(id=1, code=code)


def _dataset(code: str) -> SimpleNamespace:
    return SimpleNamespace(id=2, code=code)


def _eia_source() -> SimpleNamespace:
    return SimpleNamespace(
        id=3,
        provider_series_id="PET.RWTC.D",
        source_frequency="daily",
        source_locator={
            "route": "v2/seriesid/PET.RWTC.D",
            "expected_first_period": "1986-01-02",
        },
    )


@pytest.mark.asyncio
async def test_eia_probe_passes_only_on_pinned_minimal_series_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EIA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    raw = (FIXTURES / "eia_wti_pass.json").read_bytes()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/seriesid/PET.RWTC.D/"
        assert request.url.params["api_key"] == "probe-secret"
        assert request.url.params["length"] == "1"
        assert request.url.params["sort[0][column]"] == "period"
        assert request.url.params["sort[0][direction]"] == "asc"
        assert "start" not in request.url.params
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/json"},
            content=raw,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await EIAAdapter(client).probe(
            _provider("EIA_API_V2"), _eia_source(), _dataset("Petroleum")
        )

    assert result.classification == "PASS"
    assert result.production_ready is True
    expected_sha = "f9ebf22c8b5b50a1af8710d606d84aea3f21d1093cd913a0aab5b34e6d342c1d"
    assert result.response_sha256 == expected_sha
    assert result.request_url == "https://api.eia.gov/v2/seriesid/PET.RWTC.D/"
    assert result.official_description == "Cushing, OK WTI Spot Price FOB"
    serialized = result.to_dict()
    assert serialized["evidence"] == {
        "transport_success": True,
        "http_success": True,
        "business_success": True,
        "identity_match": True,
        "authorization_available": True,
        "details": {
            "date_format": "YYYY-MM-DD",
            "first_period": "1986-01-02",
            "frequency": "daily",
            "row_series": "PET.RWTC.D",
            "total": 1,
            "units": "$/BBL",
            "value_field": "value",
        },
    }
    assert serialized["issues"] == []
    assert "probe-secret" not in str(serialized)
    get_settings.cache_clear()
