from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from macrolens_api.config import get_settings
from macrolens_api.main import app
from macrolens_worker.providers.bls import BLSAdapter
from macrolens_worker.providers.eia import EIAAdapter
from macrolens_worker.tasks.notifications import _digest_due, _threshold_triggered

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_liveness_is_independent_from_database() -> None:
    with TestClient(app) as client:
        assert client.get("/api/v1/live").status_code == 200
        assert client.get("/api/v1/health").status_code == 200


def test_readiness_reports_database_failure(monkeypatch) -> None:
    from macrolens_api.routers import health

    async def available() -> None:
        return None

    async def unavailable() -> None:
        raise OSError("database offline")

    monkeypatch.setattr(health, "_database_ready", available)
    with TestClient(app) as client:
        assert client.get("/api/v1/ready").status_code == 200

    monkeypatch.setattr(health, "_database_ready", unavailable)
    with TestClient(app) as client:
        response = client.get("/api/v1/ready")
        assert response.status_code == 503
        assert response.json()["code"] == "database_unavailable"


def _source(source_id: int, external_id: str, *, transform: str | None = None) -> SimpleNamespace:
    locator = {} if transform is None else {"transform": transform, "periods": 1}
    return SimpleNamespace(
        id=source_id,
        provider_series_id=external_id,
        source_frequency="monthly",
        source_locator=locator,
    )


def _dataset(dataset_id: int) -> SimpleNamespace:
    return SimpleNamespace(id=dataset_id, code=f"dataset-{dataset_id}")


async def test_bls_backfill_uses_legal_windows_and_preserves_dataset_lineage(monkeypatch) -> None:
    monkeypatch.setenv("BLS_API_KEY", "test-key")
    get_settings.cache_clear()
    requests: list[dict[str, object]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        requests.append(payload)
        start = int(payload["startyear"])
        end = int(payload["endyear"])
        assert end - start + 1 <= 20
        rows = []
        if start <= 1959 <= end:
            rows.append(
                {
                    "year": "1959",
                    "period": "M12",
                    "value": "100",
                    "latest": "false",
                    "footnotes": [],
                }
            )
        if start <= 1960 <= end:
            rows.append(
                {
                    "year": "1960",
                    "period": "M01",
                    "value": "103",
                    "latest": "false",
                    "footnotes": [],
                }
            )
        series = [{"seriesID": series_id, "data": rows} for series_id in payload["seriesid"]]
        return httpx.Response(
            200, json={"status": "REQUEST_SUCCEEDED", "Results": {"series": series}}
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = BLSAdapter(client)
        first = _dataset(1)
        second = _dataset(2)
        result = await adapter.fetch(
            SimpleNamespace(code="BLS_API_V2"),
            [
                (_source(10, "SERIES_A", transform="period_difference"), first),
                (_source(20, "SERIES_B"), second),
            ],
            mode="backfill",
        )

    assert len(result) == 2
    assert {item.dataset.id for item in result} == {1, 2}
    derived = next(item for item in result if item.dataset.id == 1).observations
    january = next(item for item in derived if item.period_start.isoformat() == "1960-01-01")
    assert str(january.value) == "3"
    assert all(int(item["endyear"]) - int(item["startyear"]) + 1 <= 20 for item in requests)
    get_settings.cache_clear()


async def test_eia_adapter_paginates_until_total(monkeypatch) -> None:
    monkeypatch.setenv("EIA_API_KEY", "test-key")
    get_settings.cache_clear()
    offsets: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        rows = [
            {"period": "2026-07-01", "value": "70.1"},
            {"period": "2026-07-02", "value": "71.2"},
            {"period": "2026-07-03", "value": "72.3"},
        ][offset : offset + 2]
        return httpx.Response(200, json={"response": {"total": 3, "data": rows}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = EIAAdapter(client)
        adapter.page_size = 2
        result = await adapter.fetch(
            SimpleNamespace(code="EIA_API_V2"),
            [
                (
                    SimpleNamespace(
                        id=30,
                        source_locator={"route": "v2/seriesid/PET.RWTC.D"},
                        source_frequency="daily",
                    ),
                    _dataset(3),
                )
            ],
            mode="backfill",
        )

    assert offsets == [0, 2]
    assert len(result) == 1
    assert [str(item.value) for item in result[0].observations] == ["70.1", "71.2", "72.3"]
    get_settings.cache_clear()


def test_notification_rules_cover_supported_operators_and_cron() -> None:
    assert _threshold_triggered(3.0, ">=", 3.0)
    assert _threshold_triggered(2.9, "<", 3.0)
    assert not _threshold_triggered(2.9, ">", 3.0)
    monday_0805 = datetime(2026, 8, 3, 8, 5, tzinfo=UTC)
    assert _digest_due({"schedule": "0 8 * * 1-5"}, monday_0805, None)
    assert not _digest_due({"schedule": "0 8 * * 1-5"}, monday_0805, monday_0805)


def test_document_chunker_splits_oversized_paragraphs_with_bounded_overlap() -> None:
    from macrolens_worker.tasks.documents import _chunk_text

    text = "A" * 9500
    chunks = _chunk_text(text, max_chars=1000, overlap=100)
    assert len(chunks) > 9
    assert all(0 < len(chunk) <= 1000 for chunk in chunks)
    assert chunks[0][-100:] == chunks[1][:100]
    # Removing the overlap reconstructs the exact normalized source.
    reconstructed = chunks[0] + "".join(chunk[100:] for chunk in chunks[1:])
    assert reconstructed == text


def test_document_extractors_remove_scripts_and_read_spreadsheets() -> None:
    from io import BytesIO

    from openpyxl import Workbook

    from macrolens_worker.tasks.documents import _extract_html, _extract_xlsx

    html_text = _extract_html(
        b"<html><body><nav>menu</nav><h1>Official release</h1>"
        b"<script>steal()</script><p>Core PCE 2.6%</p></body></html>"
    )
    assert "Official release" in html_text
    assert "Core PCE 2.6%" in html_text
    assert "steal" not in html_text
    assert "menu" not in html_text

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "PCE"
    sheet.append(["period", "value"])
    sheet.append(["2026-06", 2.6])
    buffer = BytesIO()
    workbook.save(buffer)
    spreadsheet_text = _extract_xlsx(buffer.getvalue())
    assert "# PCE" in spreadsheet_text
    assert "2026-06\t2.6" in spreadsheet_text


def test_document_host_allowlist_does_not_accept_sibling_domains() -> None:
    from macrolens_worker.tasks.documents import _host_allowed

    allowed = {"bea.gov", "data.example.co.uk"}
    assert _host_allowed("apps.bea.gov", allowed)
    assert _host_allowed("data.example.co.uk", allowed)
    assert _host_allowed("files.data.example.co.uk", allowed)
    assert not _host_allowed("evilbea.gov", allowed)
    assert not _host_allowed("other.example.co.uk", allowed)


async def test_unchanged_document_parse_restores_active_status(monkeypatch) -> None:
    from uuid import uuid4

    from macrolens_worker.tasks import documents

    document = SimpleNamespace(
        id=uuid4(), source_url="https://example.com/release.txt", status="processing"
    )
    raw_object = SimpleNamespace(
        id=uuid4(),
        object_uri=f"s3://{documents.settings.s3_bucket}/raw/document.txt",
        content_type="text/plain",
    )
    existing = SimpleNamespace(id=uuid4())

    class FakeStorage:
        async def get_bytes(self, _key: str) -> bytes:
            return b"unchanged official release"

    class FakeSession:
        commits = 0

        async def get(self, model, _id):
            if model is documents.Document:
                return document
            if model is documents.RawObject:
                return raw_object
            return None

        async def scalar(self, _statement):
            return existing

        async def commit(self):
            self.commits += 1

    monkeypatch.setattr(documents, "ObjectStorage", FakeStorage)
    session = FakeSession()
    result = await documents.parse_document(  # type: ignore[arg-type]
        session,
        document_id=document.id,
        raw_object_id=raw_object.id,
    )
    assert result["status"] == "unchanged"
    assert result["version_id"] == str(existing.id)
    assert document.status == "active"
    assert session.commits == 1


def test_period_parsers_reject_invalid_quarters() -> None:
    from macrolens_worker.providers.census import CensusEITSAdapter

    assert EIAAdapter._parse_period("2026-Q1").isoformat() == "2026-01-01"
    assert EIAAdapter._parse_period("2026-Q5") is None
    assert CensusEITSAdapter._parse_period("2026-Q4").isoformat() == "2026-10-01"
    assert CensusEITSAdapter._parse_period("2026-Q0") is None
    assert CensusEITSAdapter._parse_period("2026-Q5") is None


def test_time_series_transforms_do_not_bridge_missing_months() -> None:
    from datetime import date
    from decimal import Decimal

    from macrolens_api.services.transforms import Point, transform_points

    def point(day: date, value: str) -> Point:
        return Point(day, day, Decimal(value), "normal", None, datetime.now(UTC))

    monthly = [point(date(2026, 1, 1), "100"), point(date(2026, 3, 1), "110")]
    result = transform_points(monthly, "mom", "monthly")
    assert result[1].value is None

    daily = [point(date(2025, 7, 3), "100"), point(date(2026, 7, 5), "110")]
    yoy = transform_points(daily, "yoy", "daily")
    assert yoy[1].value == Decimal("10.0")


def test_ai_data_as_of_normalizes_naive_and_aware_timestamps() -> None:
    from macrolens_api.services.ai_context import data_as_of_from_snapshots

    result = data_as_of_from_snapshots(
        [
            {"data_as_of": "2026-08-01T08:00:00"},
            {"published_at": "2026-08-01T01:30:00-07:00"},
            {"scheduled_at": "not-a-date"},
        ]
    )
    assert result.tzinfo is not None
    assert result.isoformat() == "2026-08-01T08:30:00+00:00"


def test_mock_openai_contract_over_real_http() -> None:
    import importlib.util
    import threading
    from http.server import ThreadingHTTPServer

    module_path = REPO_ROOT / "backend/tests/mock_openai_server.py"
    spec = importlib.util.spec_from_file_location("mock_openai_server", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    server = ThreadingHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        assert httpx.get(f"{base}/health", timeout=5).json() == {"ok": True}
        embeddings = httpx.post(
            f"{base}/v1/embeddings",
            json={"model": "text-embedding-3-small", "input": ["a", "b"]},
            timeout=5,
        ).json()
        assert len(embeddings["data"]) == 2
        assert len(embeddings["data"][0]["embedding"]) == 1536
        response = httpx.post(
            f"{base}/v1/responses",
            json={"model": "test-model", "input": "analyze"},
            timeout=5,
        ).json()
        assert response["status"] == "completed"
        assert "[1]" in response["output"][0]["content"][0]["text"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_initial_migration_is_self_contained_and_covers_models() -> None:
    import importlib.util
    import re

    from macrolens_api.models import Base

    migration_path = REPO_ROOT / "backend/alembic/versions/0001_initial.py"
    source = migration_path.read_text()
    assert "Base.metadata" not in source
    assert "macrolens_api.models" not in source
    spec = importlib.util.spec_from_file_location("initial_migration", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    created = {
        match.group(1)
        for statement in module.CREATE_STATEMENTS
        if (match := re.match(r"CREATE TABLE ([a-z_]+\.[a-z_]+)", statement))
    }
    assert created == set(Base.metadata.tables)
    assert len(module.DROP_STATEMENTS) == len(created)


def test_frontend_api_calls_are_represented_in_openapi() -> None:
    import re

    import yaml

    spec = yaml.safe_load((REPO_ROOT / "macrolens_openapi.yaml").read_text())
    api_paths = set(spec["paths"])
    normalized_spec = {
        re.sub(r"\{[^}]+\}", "{}", path.removeprefix("/api/v1")) for path in api_paths
    }
    missing: list[str] = []
    for page in (REPO_ROOT / "apps/web").rglob("*.tsx"):
        source = page.read_text()
        for raw in re.findall(r"apiFetch(?:<[^;()]*?>)?\(\s*([`\"'])((?:(?!\1).)*?)\1", source):
            value = raw[1]
            # Skip expressions where a conditional changes the path suffix; both branches are
            # exercised by explicit paths elsewhere in the application.
            if "${includeContent" in value:
                continue
            value = value.split("${queryString", 1)[0]
            value = re.sub(r"\$\{[^}]+\}", "{}", value)
            value = value.split("?", 1)[0]
            if value and value not in normalized_spec:
                missing.append(f"{page}:{value}")
    assert not missing, "Frontend calls missing from OpenAPI: " + ", ".join(missing)


def test_acceptance_origins_and_cookie_configuration_are_consistent() -> None:
    ci = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
    playwright = (REPO_ROOT / "apps/web/playwright.config.ts").read_text()
    env_example = (REPO_ROOT / ".env.example").read_text()
    assert "PLAYWRIGHT_BASE_URL: http://localhost:3000" in ci
    assert '"http://localhost:3000"' in playwright
    assert "WEB_ORIGIN=http://localhost:3000" in env_example


async def test_fred_adapter_normalizes_current_vintage(monkeypatch) -> None:
    from macrolens_worker.providers.fred import FREDAdapter

    monkeypatch.setenv("FRED_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["series_id"] == "PCEPI"
        if request.url.path.endswith("/fred/series"):
            return httpx.Response(
                200,
                request=request,
                json={
                    "seriess": [
                        {
                            "id": "PCEPI",
                            "frequency_short": "M",
                            "observation_start": "1959-01-01",
                            "title": "Personal Consumption Expenditures: Chain-type Price Index",
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            request=request,
            json={
                "observations": [
                    {"date": "2026-06-01", "value": "125.4", "realtime_start": "2026-07-31"},
                    {"date": "2026-07-01", "value": ".", "realtime_start": "2026-08-31"},
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await FREDAdapter(client).fetch(
            SimpleNamespace(code="FRED_API"),
            [
                (
                    SimpleNamespace(
                        id=41,
                        provider_series_id="PCEPI",
                        source_frequency="monthly",
                        source_locator={},
                    ),
                    _dataset(4),
                )
            ],
            mode="incremental",
        )
    assert len(result) == 1
    assert str(result[0].observations[0].value) == "125.4"
    assert result[0].observations[0].period_end.isoformat() == "2026-06-30"
    assert result[0].observations[1].value is None
    assert result[0].observations[0].source_updated_at.isoformat() == "2026-07-31T00:00:00+00:00"
    get_settings.cache_clear()


async def test_bea_adapter_maps_series_and_line_number(monkeypatch) -> None:
    from macrolens_worker.providers.bea import BEAAdapter

    monkeypatch.setenv("BEA_API_KEY", "test-key")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["TableName"] == "U20404"
        return httpx.Response(
            200,
            request=request,
            json={
                "BEAAPI": {
                    "Results": {
                        "Data": [
                            {
                                "SeriesCode": "DHLCRA3",
                                "LineNumber": "100",
                                "TimePeriod": "2026M06",
                                "DataValue": "132.7",
                            },
                            {
                                "SeriesCode": "OTHER",
                                "LineNumber": "101",
                                "TimePeriod": "2026M06",
                                "DataValue": "999",
                            },
                        ]
                    }
                }
            },
        )

    source = SimpleNamespace(
        id=51,
        source_locator={
            "table_name": "U20404",
            "series_code": "DHLCRA3",
            "line_number": 100,
            "frequency": "M",
        },
        source_frequency="monthly",
    )
    dataset = SimpleNamespace(id=5, code="NIUnderlyingDetail")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BEAAdapter(client).fetch(
            SimpleNamespace(code="BEA_API"), [(source, dataset)], mode="incremental"
        )
    assert len(result) == 1
    assert [
        (item.period_start.isoformat(), str(item.value)) for item in result[0].observations
    ] == [
        ("2026-06-01", "132.7"),
    ]
    get_settings.cache_clear()


async def test_census_adapter_requires_dimensions_and_parses_matrix(monkeypatch) -> None:
    from datetime import date as dt_date

    from macrolens_worker.providers.census import CensusEITSAdapter

    monkeypatch.setenv("CENSUS_API_KEY", "test-key")
    get_settings.cache_clear()
    current_year = dt_date.today().year

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["time"] == f"from+{current_year - 5}+to+{current_year}"
        payload = [
            ["cell_value", "time", "time_slot_date", "seasonally_adj"],
            ["42.5", f"{current_year}-01", f"{current_year}-01-01", "yes"],
        ]
        return httpx.Response(200, request=request, json=payload)

    ready = SimpleNamespace(
        id=61,
        source_locator={
            "path": "timeseries/eits/marts",
            "value_field": "cell_value",
            "time_field": "time",
            "dimensions": {"seasonally_adj": "yes"},
        },
        source_frequency="monthly",
    )
    unresolved = SimpleNamespace(
        id=62,
        source_locator={"path": "timeseries/eits/marts", "dimensions": {}},
        source_frequency="monthly",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await CensusEITSAdapter(client).fetch(
            SimpleNamespace(code="CENSUS_EITS_API"),
            [(ready, _dataset(6))],
            mode="incremental",
        )
    assert len(result) == 1
    assert result[0].dataset.id == 6
    assert result[0].observations[0].period_start.year == current_year
    assert str(result[0].observations[0].value) == "42.5"
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(RuntimeError, match="no pinned dimensions"):
            await CensusEITSAdapter(client).fetch(
                SimpleNamespace(code="CENSUS_EITS_API"),
                [(unresolved, _dataset(7))],
                mode="incremental",
            )
    get_settings.cache_clear()


async def test_dol_adapter_supports_json_and_csv(monkeypatch) -> None:
    from macrolens_worker.providers.dol import DOLOpenDataAdapter

    monkeypatch.setenv("DOL_CLAIMS_URL", "https://dol.example/claims")
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/json"},
            json={
                "records": [
                    {"week_ending": "2026-07-25", "initial_claims_seasonally_adjusted": "221000"}
                ]
            },
        )

    source = SimpleNamespace(id=71, source_locator={}, source_frequency="weekly")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await DOLOpenDataAdapter(client).fetch(
            SimpleNamespace(code="DOL_OPEN_DATA_API"), [(source, _dataset(8))], mode="incremental"
        )
    assert str(result[0].observations[0].value) == "221000"
    assert result[0].observations[0].period_end.isoformat() == "2026-07-31"
    csv_rows = DOLOpenDataAdapter._rows(b"week_ending,claims\n2026-07-25,221000\n", "text/csv")
    assert csv_rows[0]["claims"] == "221000"
    get_settings.cache_clear()


async def test_nyfed_adapter_discovers_nested_rows() -> None:
    from macrolens_worker.providers.nyfed import NYFedAdapter

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"refRates": {"rates": [{"effectiveDate": "2026-07-31", "percentRate": "5.31"}]}},
        )

    source = SimpleNamespace(
        id=81,
        source_locator={"route": "rates/secured/sofr/last/1.json"},
        source_frequency="daily",
        provider_series_id="SOFR",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await NYFedAdapter(client).fetch(
            SimpleNamespace(code="NYFED_MARKETS_API"), [(source, _dataset(9))], mode="incremental"
        )
    assert len(result[0].observations) == 1
    assert str(result[0].observations[0].value) == "5.31"


async def test_treasury_adapter_parses_nominal_and_real_xml() -> None:
    from macrolens_worker.providers.treasury import TreasuryAdapter

    async def handler(request: httpx.Request) -> httpx.Response:
        year = request.url.params["field_tdr_date_value"]
        xml = (
            '<?xml version="1.0"?><feed xmlns:d="x" xmlns:m="y">'
            "<entry><content><m:properties>"
            f"<d:NEW_DATE>{year}-07-31T00:00:00</d:NEW_DATE>"
            "<d:BC_2YEAR>4.10</d:BC_2YEAR><d:BC_10YEAR>4.35</d:BC_10YEAR>"
            "<d:TC_10YEAR>1.98</d:TC_10YEAR>"
            "</m:properties></content></entry></feed>"
        ).encode()
        return httpx.Response(
            200, request=request, content=xml, headers={"content-type": "application/xml"}
        )

    nominal = SimpleNamespace(id=91, provider_series_id="2Y_PAR_NOMINAL", source_frequency="daily")
    real = SimpleNamespace(id=92, provider_series_id="10Y_PAR_REAL", source_frequency="daily")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await TreasuryAdapter(client).fetch(
            SimpleNamespace(code="US_TREASURY_XML"),
            [(nominal, _dataset(10)), (real, _dataset(11))],
            mode="incremental",
        )
    values = [
        (item.observations[0].source_series_id, str(item.observations[0].value))
        for item in result
        if item.observations
    ]
    assert (91, "4.10") in values
    assert (92, "1.98") in values


def test_release_calendar_and_fomc_helpers_cover_realistic_formats() -> None:
    from datetime import date as dt_date

    from macrolens_worker.tasks.fomc import _document_type, _meeting_dates
    from macrolens_worker.tasks.release_calendar import _event_datetime, _match_release, parse_ics

    raw = (
        "BEGIN:VCALENDAR\r\n"
        "BEGIN:VEVENT\r\n"
        "UID:test-1\r\n"
        "SUMMARY:Employment Situation\r\n"
        "DTSTART;TZID=America/New_York:20260807T083000\r\n"
        "DESCRIPTION:Line one\\n line two\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    events = parse_ics(raw)
    assert events[0]["SUMMARY"] == "Employment Situation"
    assert _event_datetime(events[0]).isoformat() == "2026-08-07T12:30:00+00:00"
    assert _match_release(events[0]["SUMMARY"])[0] == "EMPLOYMENT"
    assert _meeting_dates(2026, "September", "15-16") == (
        dt_date(2026, 9, 15),
        dt_date(2026, 9, 16),
    )
    assert _document_type("Minutes", "/minutes.pdf") == "minutes"
    assert _document_type("Summary of Economic Projections", "/sep.pdf") == "projection"


async def test_worker_health_server_exposes_cloud_run_port(monkeypatch) -> None:
    import asyncio
    import socket

    from macrolens_worker.health import health_server

    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    monkeypatch.setenv("PORT", str(port))
    task = asyncio.create_task(health_server("worker-test"))
    try:
        for _ in range(50):
            try:
                reader, writer = await asyncio.open_connection("127.0.0.1", port)
                break
            except OSError:
                await asyncio.sleep(0.01)
        else:
            raise AssertionError("health server did not bind")
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        raw = await reader.read()
        writer.close()
        await writer.wait_closed()
        assert b"HTTP/1.1 200 OK" in raw
        assert b'"role":"worker-test"' in raw
    finally:
        task.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await task
