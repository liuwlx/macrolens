from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from macrolens_api.config import get_settings
from macrolens_worker.providers.fred import FREDAdapter
from macrolens_worker.providers.nyfed import NYFedAdapter
from macrolens_worker.providers.treasury import TreasuryAdapter


def _provider(code: str) -> SimpleNamespace:
    return SimpleNamespace(id=1, code=code)


def _dataset(code: str) -> SimpleNamespace:
    return SimpleNamespace(id=2, code=code)


@pytest.mark.asyncio
async def test_fred_probe_requires_metadata_identity_and_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FRED_API_KEY", "fred-probe-secret")
    get_settings.cache_clear()
    source = SimpleNamespace(
        id=7,
        provider_series_id="NFCI",
        source_frequency="weekly",
        source_locator={
            "expected_first_period": "1971-01-08",
            "expected_title": "Chicago Fed National Financial Conditions Index",
        },
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/fred/series"
        assert request.url.params["series_id"] == "NFCI"
        assert request.url.params["api_key"] == "fred-probe-secret"
        return httpx.Response(
            200,
            request=request,
            json={
                "seriess": [
                    {
                        "id": "NFCI",
                        "title": "Chicago Fed National Financial Conditions Index",
                        "frequency_short": "W",
                        "observation_start": "1971-01-08",
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await FREDAdapter(client).probe(_provider("FRED_API"), source, _dataset("NFCI"))

    assert result.classification == "PASS"
    assert result.official_description == "Chicago Fed National Financial Conditions Index"
    assert result.evidence is not None
    assert result.evidence.details["frequency"] == "W"
    assert "fred-probe-secret" not in str(result.to_dict())
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_nyfed_probe_accepts_pinned_rate_route_and_numeric_row() -> None:
    source = SimpleNamespace(
        id=8,
        provider_series_id="SOFR",
        source_frequency="daily",
        source_locator={
            "route": "rates/secured/sofr/search.json",
            "type": "rate",
        },
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/rates/secured/sofr/search.json")
        assert request.url.params["format"] == "json"
        return httpx.Response(
            200,
            request=request,
            json={"refRates": [{"effectiveDate": "2026-08-14", "percentRate": "3.67"}]},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await NYFedAdapter(client).probe(
            _provider("NYFED_MARKETS_API"), source, _dataset("Reference Rates")
        )

    assert result.classification == "PASS"
    assert result.official_description == "SOFR"
    assert result.evidence is not None
    assert result.evidence.details["first_period"] == "2026-08-14"


@pytest.mark.asyncio
async def test_treasury_probe_requires_the_pinned_field_and_non_null_value() -> None:
    source = SimpleNamespace(
        id=9,
        provider_series_id="10Y_PAR_NOMINAL",
        source_frequency="daily",
        source_locator={"start_year": 1990},
    )
    xml = b"""
    <feed xmlns='http://www.w3.org/2005/Atom'>
      <entry><content><properties xmlns='http://schemas.microsoft.com/ado/2007/08/dataservices/metadata'>
        <NEW_DATE xmlns='http://schemas.microsoft.com/ado/2007/08/dataservices'>2026-08-14</NEW_DATE>
        <BC_10YEAR xmlns='http://schemas.microsoft.com/ado/2007/08/dataservices'>4.25</BC_10YEAR>
      </properties></content></entry>
    </feed>
    """

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/interest-rates/pages/xml")
        assert request.url.params["data"] == "daily_treasury_yield_curve"
        return httpx.Response(200, request=request, content=xml)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TreasuryAdapter(client).probe(
            _provider("US_TREASURY_XML"), source, _dataset("Daily Treasury Interest Rates")
        )

    assert result.classification == "PASS"
    assert result.official_description == "10Y_PAR_NOMINAL"
    assert result.evidence is not None
    assert result.evidence.details["observation_count"] == 1
