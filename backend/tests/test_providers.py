from datetime import date
from types import SimpleNamespace

from macrolens_worker.providers.census import CensusEITSAdapter
from macrolens_worker.providers.treasury import TreasuryAdapter


def source(source_id: int, code: str, frequency: str = "daily") -> SimpleNamespace:
    return SimpleNamespace(id=source_id, provider_series_id=code, source_frequency=frequency)


def test_census_period_parser() -> None:
    assert CensusEITSAdapter._parse_period("2026-07") == date(2026, 7, 1)
    assert CensusEITSAdapter._parse_period("2026-Q3") == date(2026, 7, 1)
    assert CensusEITSAdapter._parse_period("2026") == date(2026, 1, 1)
    assert CensusEITSAdapter._parse_period("bad") is None


def test_treasury_xml_parser() -> None:
    raw = b"""<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata"
          xmlns:d="http://schemas.microsoft.com/ado/2007/08/dataservices">
      <entry><content><m:properties>
        <d:NEW_DATE>2026-07-31T00:00:00</d:NEW_DATE>
        <d:BC_2YEAR>4.10</d:BC_2YEAR>
        <d:BC_10YEAR>4.35</d:BC_10YEAR>
      </m:properties></content></entry>
    </feed>"""
    adapter = TreasuryAdapter(client=None)  # type: ignore[arg-type]
    rows = adapter._parse(
        raw,
        [
            (source(1, "2Y_PAR_NOMINAL"), SimpleNamespace()),
            (source(2, "10Y_PAR_NOMINAL"), SimpleNamespace()),
        ],
    )
    assert len(rows) == 2
    assert rows[0].period_start == date(2026, 7, 31)
    assert str(rows[0].value) == "4.10"
    assert str(rows[1].value) == "4.35"
