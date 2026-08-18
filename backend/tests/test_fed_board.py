from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from macrolens_worker.providers.base import ProviderDataError
from macrolens_worker.providers.fed_board import FederalReserveBoardAdapter

G17_SAMPLE = (
    b'"B50001: Total index"\n'
    b'"B50001" 1919 4.8739 4.6585 4.5238 4.6046 4.6315 4.9277 '
    b'5.2239 5.3047 5.1970 5.1432 5.0624 5.1432\n'
    b'"B50001" 1920 5.6279 5.6279 5.5201 5.2239 5.3586 5.4124 '
    b'5.2778 5.3047 5.1162 4.9008 4.4969 4.2276\n'
)


def _source(locator: dict[str, object]) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        provider_series_id="B50001",
        source_frequency="monthly",
        source_locator=locator,
    )


def _dataset() -> SimpleNamespace:
    return SimpleNamespace(code="G17")


def test_g17_parser_normalizes_year_month_rows() -> None:
    source = _source(
        {
            "series_code": "B50001",
            "line_description": "Total index",
            "expected_first_period": "1919-01-01",
        }
    )
    rows = FederalReserveBoardAdapter._parse_g17(G17_SAMPLE, source, vintage_at=None)

    assert len(rows) == 24
    assert rows[0].period_start == date(1919, 1, 1)
    assert rows[0].period_end == date(1919, 1, 31)
    assert str(rows[0].value) == "4.8739"
    assert rows[-1].period_start == date(1920, 12, 1)


def test_g17_parser_rejects_identity_drift() -> None:
    source = _source(
        {
            "series_code": "B50001",
            "line_description": "Industrial production",
            "expected_first_period": "1919-01-01",
        }
    )

    with pytest.raises(ProviderDataError, match="line_description"):
        FederalReserveBoardAdapter._parse_g17(G17_SAMPLE, source, vintage_at=None)


def test_g17_parser_rejects_rows_without_twelve_months() -> None:
    source = _source(
        {
            "series_code": "B50001",
            "line_description": "Total index",
            "expected_first_period": "1919-01-01",
        }
    )
    malformed = b'"B50001: Total index"\n"B50001" 1919 1 2 3\n'

    with pytest.raises(ProviderDataError, match="12 monthly values"):
        FederalReserveBoardAdapter._parse_g17(malformed, source, vintage_at=None)


def test_g17_parser_allows_partial_latest_year_only_when_configured() -> None:
    source = _source(
        {
            "series_code": "B50001",
            "line_description": "Total index",
            "expected_first_period": "1919-01-01",
            "allow_partial_latest_year": True,
        }
    )
    partial = G17_SAMPLE + b'"B50001" 1921 1 2 3 4 5 6\n'

    rows = FederalReserveBoardAdapter._parse_g17(partial, source, vintage_at=None)

    assert len(rows) == 30
    assert rows[-1].period_start == date(1921, 6, 1)


async def test_g17_fetch_preserves_official_raw_bytes() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            content=G17_SAMPLE,
            headers={
                "content-type": "text/plain",
                "last-modified": "Tue, 18 Aug 2026 12:00:00 GMT",
            },
        )

    source = _source(
        {
            "file_url": "https://www.federalreserve.gov/releases/g17/current/ipdisk/ip_sa.txt",
            "series_code": "B50001",
            "line_description": "Total index",
            "expected_first_period": "1919-01-01",
        }
    )
    provider = SimpleNamespace(code="FED_BOARD_FILES")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await FederalReserveBoardAdapter(client).fetch(
            provider, [(source, _dataset())], mode="backfill"
        )

    assert results[0].raw_bytes == G17_SAMPLE
    assert len(results[0].observations) == 24
    assert results[0].request_parameters["file_url"].endswith("ip_sa.txt")
