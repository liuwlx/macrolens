from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from macrolens_api.config import get_settings
from macrolens_worker.providers.base import (
    MappingProbeEvidence,
    MappingProbeResult,
    ProviderDataError,
)
from macrolens_worker.providers.bea import BEAAdapter
from macrolens_worker.providers.bls import BLSAdapter
from macrolens_worker.providers.census import CensusEITSAdapter
from macrolens_worker.providers.eia import EIAAdapter

FIXTURES = Path(__file__).parent / "fixtures/mapping_probes"


def _provider(code: str) -> SimpleNamespace:
    return SimpleNamespace(id=1, code=code)


def _dataset(code: str) -> SimpleNamespace:
    return SimpleNamespace(id=2, code=code)


def _eia_source(**locator_overrides: object) -> SimpleNamespace:
    locator = {
        "route": "v2/seriesid/PET.RWTC.D",
        "expected_first_period": "1986-01-02",
        "min_observations_backfill": 100,
    }
    locator.update(locator_overrides)
    return SimpleNamespace(
        id=3,
        provider_series_id="PET.RWTC.D",
        source_frequency="daily",
        source_locator=locator,
    )


def _bea_source(**locator_overrides: object) -> SimpleNamespace:
    locator = {
        "table_name": "U20404",
        "frequency": "M",
        "series_code": "DHLCRA3",
        "line_number": "100",
        "line_description": "Health care services",
        "probe_year": "2025",
        "metric_name": "Price index",
        "cl_unit": "Index",
        "unit_mult": "0",
    }
    locator.update(locator_overrides)
    return SimpleNamespace(
        id=4,
        provider_series_id=None,
        source_frequency="monthly",
        source_locator=locator,
    )


def _census_source(**locator_overrides: object) -> SimpleNamespace:
    locator = {
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
    }
    locator.update(locator_overrides)
    return SimpleNamespace(
        id=5,
        provider_series_id=None,
        source_frequency="monthly",
        source_locator=locator,
    )


def _assert_secret_absent(value: Any, secret: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            assert secret not in str(key)
            _assert_secret_absent(item, secret)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _assert_secret_absent(item, secret)
    elif isinstance(value, bytes):
        assert secret.encode() not in value
    else:
        assert secret not in str(value)


@pytest.mark.asyncio
async def test_eia_probe_passes_only_on_pinned_minimal_series_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EIA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    latest_raw = (
        b'{"response":{"total":"10225","frequency":"daily",'
        b'"dateFormat":"YYYY-MM-DD","description":"Cushing, OK WTI Spot Price FOB",'
        b'"data":[{"period":"2026-08-10","series":"RWTC","value":"63.96",'
        b'"units":"$/BBL"}]}}'
    )
    first_raw = (
        b'{"response":{"total":"10225","frequency":"daily",'
        b'"dateFormat":"YYYY-MM-DD","description":"Cushing, OK WTI Spot Price FOB",'
        b'"data":[{"period":"1986-01-02","series":"RWTC","value":"25.56",'
        b'"units":"$/BBL"}]}}'
    )
    offsets: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/seriesid/PET.RWTC.D/"
        assert request.url.params["api_key"] == "probe-secret"
        assert request.url.params["length"] == "1"
        assert "sort[0][column]" not in request.url.params
        assert "sort[0][direction]" not in request.url.params
        assert "start" not in request.url.params
        offset = int(request.url.params["offset"])
        offsets.append(offset)
        return httpx.Response(
            200,
            request=request,
            headers={"content-type": "application/json"},
            content=latest_raw if offset == 0 else first_raw,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await EIAAdapter(client).probe(
            _provider("EIA_API_V2"), _eia_source(), _dataset("Petroleum")
        )

    assert result.classification == "PASS"
    assert result.production_ready is True
    assert offsets == [0, 10224]
    expected_sha = "823278703dfb98583d719927d7f008fbf5fe3376fe16fc357ef5d4cac243b452"
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
            "first_value": "25.56",
            "frequency": "daily",
            "row_series": "RWTC",
            "total": 10225,
            "units": "$/BBL",
            "value_field": "value",
        },
    }
    assert serialized["issues"] == []
    assert "probe-secret" not in str(serialized)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_bea_probe_passes_only_on_unique_fully_pinned_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    raw = (FIXTURES / "bea_pce_pass.json").read_bytes()
    source = _bea_source(line_description="  Health   care services ")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/data"
        assert request.url.params["UserID"] == "probe-secret"
        assert request.url.params["method"] == "GetData"
        assert request.url.params["DataSetName"] == "NIUnderlyingDetail"
        assert request.url.params["TableName"] == "U20404"
        assert request.url.params["Frequency"] == "M"
        assert request.url.params["Year"] == "2025"
        return httpx.Response(200, request=request, content=raw)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BEAAdapter(client).probe(
            _provider("BEA_API"), source, _dataset("NIUnderlyingDetail")
        )

    assert result.classification == "PASS"
    assert result.provider_series_id is None
    expected_sha = "ec36476c1acbb760139727278c167544b5166ead8baf557773ef95f872695509"
    assert result.response_sha256 == expected_sha
    assert result.request_url == "https://apps.bea.gov/api/data"
    assert result.official_description == "Health care services"
    assert result.evidence is not None
    assert result.evidence.details == {
        "cl_unit": "Index",
        "frequency": "M",
        "line_description": "Health care services",
        "line_number": "100",
        "metric_name": "Price index",
        "series_code": "DHLCRA3",
        "table_name": "U20404",
        "time_period": "2025M01",
        "unit_mult": "0",
    }
    assert result.issues == ()
    assert "probe-secret" not in str(result.to_dict())
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_bea_probe_compares_numeric_zero_unit_multiplier_strictly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "bea_pce_pass.json").read_text())
    body["BEAAPI"]["Results"]["Data"][0]["UNIT_MULT"] = 0

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BEAAdapter(client).probe(
            _provider("BEA_API"),
            _bea_source(unit_mult=0),
            _dataset("NIUnderlyingDetail"),
        )

    assert result.classification == "PASS"
    assert result.evidence is not None
    assert result.evidence.details["unit_mult"] == "0"
    get_settings.cache_clear()


async def test_bea_probe_keeps_unit_multiplier_identity_with_platform_scale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    body = {
        "BEAAPI": {
            "Results": {
                "Data": [
                    {
                        "SeriesCode": "A191RX",
                        "LineNumber": "1",
                        "LineDescription": "Gross domestic product",
                        "TimePeriod": "2025Q1",
                        "DataValue": "23,548,210",
                        "METRIC_NAME": "Chained Dollars",
                        "CL_UNIT": "Level",
                        "UNIT_MULT": "6",
                    }
                ]
            }
        }
    }

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BEAAdapter(client).probe(
            _provider("BEA_API"),
            _bea_source(
                table_name="T10106",
                frequency="Q",
                series_code="A191RX",
                line_number="1",
                line_description="Gross domestic product",
                probe_year="2025",
                metric_name="Chained Dollars",
                cl_unit="Level",
                unit_mult="6",
                value_scale_to_platform_unit="0.001",
            ),
            _dataset("NIPA"),
        )

    assert result.classification == "PASS"
    assert result.evidence is not None
    assert result.evidence.details["unit_mult"] == "6"
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_census_probe_passes_on_one_exact_month_and_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CENSUS_API_KEY", "probe-secret")
    get_settings.cache_clear()
    body = [
        [
            "cell_value",
            "time",
            "data_type_code",
            "seasonally_adj",
            "category_code",
            "error_data",
            "us",
        ],
        ["9.9", "2025-01", "SM", "yes", "441", "no", "1"],
        ["42.5", "2025-01", "SM", "yes", "44X72", "no", "1"],
    ]
    raw = json.dumps(body, separators=(",", ":")).encode()
    source = _census_source(
        required_variables=[
            "data_type_code",
            "seasonally_adj",
            "category_code",
            "cell_value",
            "error_data",
            "time",
        ],
        dimensions={
            "data_type_code": "SM",
            "seasonally_adj": "yes",
            "category_code": "44X72",
            "error_data": "no",
            "for": "us:*",
        },
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/data/timeseries/eits/marts"
        assert request.url.params["key"] == "probe-secret"
        assert request.url.params["time"] == "2025-01"
        assert request.url.params["for"] == "us:*"
        assert set(request.url.params) == {"get", "time", "key", "for"}
        requested = set(request.url.params["get"].split(","))
        assert requested == {
            "cell_value",
            "data_type_code",
            "seasonally_adj",
            "category_code",
            "error_data",
        }
        return httpx.Response(200, request=request, content=raw)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await CensusEITSAdapter(client).probe(
            _provider("CENSUS_EITS_API"), source, _dataset("marts")
        )

    assert result.classification == "PASS"
    assert result.provider_series_id is None
    expected_sha = "4b95060ef479502408927650e8fd2741a28b185677c5a0916b9968aa7b0901f8"
    assert result.response_sha256 == expected_sha
    assert result.request_url == "https://api.census.gov/data/timeseries/eits/marts"
    assert result.evidence is not None
    assert result.evidence.details == {
        "dimensions": {
            "category_code": "44X72",
            "data_type_code": "SM",
            "error_data": "no",
            "seasonally_adj": "yes",
        },
        "geography": {"us": "1"},
        "headers": [
            "cell_value",
            "time",
            "data_type_code",
            "seasonally_adj",
            "category_code",
            "error_data",
            "us",
        ],
        "time": "2025-01",
        "value": "42.5",
        "value_field": "cell_value",
    }
    assert result.issues == ()
    assert "probe-secret" not in str(result.to_dict())
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_code", "expected_classification"),
    [
        ("auth", "authorization_missing", "AUTH_REQUIRED"),
        ("transport", "transport_error", "BLOCKED"),
        ("http", "http_status", "BLOCKED"),
        ("business", "business_error", "BLOCKED"),
        ("identity", "frequency_drift", "BLOCKED"),
    ],
)
async def test_eia_probe_failure_matrix_is_fail_closed_and_secret_safe(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_code: str,
    expected_classification: str,
) -> None:
    secret = "eia-recursive-key-sentinel"
    if case == "auth":
        monkeypatch.delenv("EIA_API_KEY", raising=False)
    else:
        monkeypatch.setenv("EIA_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "eia_wti_pass.json").read_text())
    body["response"]["data"][0]["series"] = "RWTC"
    if case == "business":
        body = {"error": {"message": secret}}
    elif case == "identity":
        body["response"]["frequency"] = "weekly"
    raw = secret.encode() if case == "http" else json.dumps(body, separators=(",", ":")).encode()
    expected_sha = {
        "auth": "9c10cbd5f5e646d0ae1f70d175b9d9f9fcd4fb3dafc1018a16d0d554bc4ff007",
        "business": "8bb66af36c2f2000d439e675ffeb39c2376ef1cd7eacaad7f606146beb13e3cf",
        "http": "d46732b19ee2ee29b26462c07cba60a0e1b65624310eb126831560dbaaa37051",
        "identity": "385d9b45da68e6e3299b5a314e37e14a98c1fb94a6bd82a2234d2e3ec29d77b8",
        "transport": "",
    }[case]

    async def handler(request: httpx.Request) -> httpx.Response:
        if case == "transport":
            raise httpx.ConnectError(secret, request=request)
        return httpx.Response(503 if case == "http" else 200, request=request, content=raw)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await EIAAdapter(client).probe(
            _provider("EIA_API_V2"), _eia_source(), _dataset("Petroleum")
        )

    assert result.classification == expected_classification
    assert result.production_ready is False
    assert expected_code in {issue.code for issue in result.issues}
    assert result.response_sha256 == expected_sha
    _assert_secret_absent(result.to_dict(), secret)
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["v2/petroleum/pri/spt/data", "/v2/seriesid/PET.RWTC.D/"])
async def test_eia_probe_rejects_route_drift_before_http(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
) -> None:
    monkeypatch.setenv("EIA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request)

    source = _eia_source()
    source.source_locator["route"] = route
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await EIAAdapter(client).probe(
            _provider("EIA_API_V2"), source, _dataset("Petroleum")
        )

    assert called is False
    assert result.classification == "BLOCKED"
    assert {issue.code for issue in result.issues} == {"route_not_pinned"}
    assert result.response_sha256 == ""
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_eia_probe_blocks_total_below_pinned_backfill_minimum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EIA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    source = _eia_source()
    body = json.loads((FIXTURES / "eia_wti_pass.json").read_text())
    body["response"]["total"] = "99"
    body["response"]["data"][0]["series"] = "RWTC"
    raw = json.dumps(body, separators=(",", ":")).encode()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=raw)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await EIAAdapter(client).probe(
            _provider("EIA_API_V2"), source, _dataset("Petroleum")
        )

    assert result.classification == "BLOCKED"
    assert {issue.code for issue in result.issues} == {"total_below_minimum"}
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "minimum"),
    [
        ("missing", None),
        ("not-an-integer", "many"),
        ("below-minimum", 1),
    ],
)
async def test_eia_probe_requires_fixed_backfill_minimum_before_http(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    minimum: object,
) -> None:
    monkeypatch.setenv("EIA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    source = _eia_source(min_observations_backfill=minimum)
    if case == "missing":
        source.source_locator.pop("min_observations_backfill")
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(
            200,
            request=request,
            content=(FIXTURES / "eia_wti_pass.json").read_bytes(),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await EIAAdapter(client).probe(
            _provider("EIA_API_V2"), source, _dataset("Petroleum")
        )

    assert called is False
    assert result.classification == "BLOCKED"
    assert {issue.code for issue in result.issues} == {
        "min_observations_backfill_invalid"
    }
    assert result.response_sha256 == ""
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_eia_probe_redacts_success_payload_before_extracting_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "eia-success-payload-secret"
    monkeypatch.setenv("EIA_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "eia_wti_pass.json").read_text())
    body["response"]["data"][0]["series"] = "RWTC"
    body["response"]["description"] = f"description echoed {secret}"
    body["response"]["data"][0]["value"] = secret
    raw = json.dumps(body, separators=(",", ":")).encode()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=raw)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await EIAAdapter(client).probe(
            _provider("EIA_API_V2"), _eia_source(), _dataset("Petroleum")
        )

    expected_sha = "a3d0642a8ef9bcb0d14cf4ba1c3de45438af4a8a013b9a43071d00efcbd99788"
    assert result.response_sha256 == expected_sha
    assert result.classification == "BLOCKED"
    assert "value_invalid" in {issue.code for issue in result.issues}
    _assert_secret_absent(result.to_dict(), secret)
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_code", "expected_classification"),
    [
        ("auth", "authorization_missing", "AUTH_REQUIRED"),
        ("transport", "transport_error", "BLOCKED"),
        ("http", "http_status", "BLOCKED"),
        ("business_top", "business_error", "BLOCKED"),
        ("business_results", "business_error", "BLOCKED"),
        ("business_results_list", "business_error", "BLOCKED"),
        ("identity", "line_description_drift", "BLOCKED"),
    ],
)
async def test_bea_probe_failure_matrix_is_fail_closed_and_secret_safe(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_code: str,
    expected_classification: str,
) -> None:
    secret = "bea-recursive-key-sentinel"
    if case == "auth":
        monkeypatch.delenv("BEA_API_KEY", raising=False)
    else:
        monkeypatch.setenv("BEA_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "bea_pce_pass.json").read_text())
    if case == "business_top":
        body = {"BEAAPI": {"Error": {"APIErrorDescription": secret}}}
    elif case == "business_results":
        body = {"BEAAPI": {"Results": {"Error": {"APIErrorDescription": secret}}}}
    elif case == "business_results_list":
        body = {"BEAAPI": {"Results": [{"Error": {"APIErrorDescription": secret}}]}}
    elif case == "identity":
        body["BEAAPI"]["Results"]["Data"][0]["LineDescription"] = "Hospital services"

    async def handler(request: httpx.Request) -> httpx.Response:
        if case == "transport":
            raise httpx.ConnectError(secret, request=request)
        if case == "http":
            return httpx.Response(429, request=request, content=secret.encode())
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BEAAdapter(client).probe(
            _provider("BEA_API"), _bea_source(), _dataset("NIUnderlyingDetail")
        )

    assert result.classification == expected_classification
    assert expected_code in {issue.code for issue in result.issues}
    _assert_secret_absent(result.to_dict(), secret)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_bea_probe_blocks_unpinned_identity_without_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BEA_API_KEY", "probe-secret")
    get_settings.cache_clear()
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request)

    source = _bea_source(frequency="", series_code="", line_number="", line_description="")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BEAAdapter(client).probe(
            _provider("BEA_API"), source, _dataset("NIUnderlyingDetail")
        )

    assert called is False
    assert result.classification == "BLOCKED"
    assert {issue.code for issue in result.issues} == {
        "frequency_missing",
        "line_description_missing",
        "line_number_missing",
        "series_code_missing",
    }
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("case", "expected_code", "expected_classification"),
    [
        ("auth", "authorization_missing", "AUTH_REQUIRED"),
        ("transport", "transport_error", "BLOCKED"),
        ("http", "http_status", "BLOCKED"),
        ("business", "business_error", "BLOCKED"),
        ("geography", "geography_drift", "BLOCKED"),
        ("headers", "headers_mismatch", "BLOCKED"),
        ("identity", "dimensions_drift", "BLOCKED"),
        ("duplicate", "row_count_invalid", "BLOCKED"),
    ],
)
async def test_census_probe_failure_matrix_is_fail_closed_and_secret_safe(
    monkeypatch: pytest.MonkeyPatch,
    case: str,
    expected_code: str,
    expected_classification: str,
) -> None:
    secret = "census-recursive-key-sentinel"
    if case == "auth":
        monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    else:
        monkeypatch.setenv("CENSUS_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "census_retail_pass.json").read_text())
    if case == "business":
        body = {"error": secret}
    elif case == "geography":
        body[1][4] = "2"
    elif case == "headers":
        body[0].append("unexpected_field")
        body[1].append("unexpected")
    elif case == "identity":
        body[1][3] = "MOTOR_VEHICLES"
    elif case == "duplicate":
        body.append(list(body[1]))

    async def handler(request: httpx.Request) -> httpx.Response:
        if case == "transport":
            raise httpx.ConnectError(secret, request=request)
        if case == "http":
            return httpx.Response(500, request=request, content=secret.encode())
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await CensusEITSAdapter(client).probe(
            _provider("CENSUS_EITS_API"), _census_source(), _dataset("marts")
        )

    assert result.classification == expected_classification
    assert expected_code in {issue.code for issue in result.issues}
    _assert_secret_absent(result.to_dict(), secret)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_census_probe_redacts_success_payload_before_extracting_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hashlib import sha256

    secret = "census-success-payload-secret"
    monkeypatch.setenv("CENSUS_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "census_retail_pass.json").read_text())
    body[0][0] = f"cell_value-{secret}"
    body[1][0] = secret
    body[1][2] = secret
    raw = json.dumps(body, separators=(",", ":")).encode()

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, content=raw)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await CensusEITSAdapter(client).probe(
            _provider("CENSUS_EITS_API"), _census_source(), _dataset("marts")
        )

    assert result.response_sha256 == sha256(raw).hexdigest()
    assert result.classification == "BLOCKED"
    assert {"headers_mismatch", "dimensions_drift", "value_invalid"} <= {
        issue.code for issue in result.issues
    }
    _assert_secret_absent(result.to_dict(), secret)
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "locator_overrides",
    [
        {"resolve_dimensions_from_dictionary": True},
        {"path": ""},
        {"value_field": ""},
        {"time_field": ""},
        {"required_variables": []},
        {"dimensions": {"seasonally_adj": "", "for": "us:*"}},
    ],
)
async def test_census_probe_blocks_unresolved_locator_before_http(
    monkeypatch: pytest.MonkeyPatch,
    locator_overrides: dict[str, object],
) -> None:
    monkeypatch.setenv("CENSUS_API_KEY", "probe-secret")
    get_settings.cache_clear()
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await CensusEITSAdapter(client).probe(
            _provider("CENSUS_EITS_API"),
            _census_source(**locator_overrides),
            _dataset("marts"),
        )

    assert called is False
    assert result.classification == "BLOCKED"
    assert result.response_sha256 == ""
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "dimensions",
    [
        {"seasonally_adj": "yes", "category_code": "TOTAL"},
        {"seasonally_adj": "yes", "category_code": "TOTAL", "for": "state:*"},
    ],
)
async def test_census_probe_requires_us_country_predicate_before_http(
    monkeypatch: pytest.MonkeyPatch,
    dimensions: dict[str, str],
) -> None:
    monkeypatch.setenv("CENSUS_API_KEY", "probe-secret")
    get_settings.cache_clear()
    called = False

    async def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, request=request, json=[])

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await CensusEITSAdapter(client).probe(
            _provider("CENSUS_EITS_API"),
            _census_source(dimensions=dimensions),
            _dataset("marts"),
        )

    assert called is False
    assert result.classification == "BLOCKED"
    assert {issue.code for issue in result.issues} == {"country_predicate_invalid"}
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_bls_probe_preserves_legacy_fields_and_adds_structured_issues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    get_settings.cache_clear()
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/bls/cpi_headline_2025.json").read_text()
    )
    body = fixture["responses"][0]
    source = SimpleNamespace(
        id=42,
        provider_series_id="CUSR0000SA0",
        source_frequency="monthly",
        source_locator={
            "expected_catalog_title": (
                "All items in U.S. city average, all urban consumers, seasonally adjusted"
            )
        },
    )

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await BLSAdapter(client).probe(
            _provider("BLS_API_V2"), source, _dataset("Public Data API")
        )

    assert result.classification == "AUTH_REQUIRED"
    assert result.http_reachable is True
    assert result.business_success is True
    assert result.identity_match is True
    assert result.evidence is not None
    assert result.evidence.authorization_available is False
    assert [issue.code for issue in result.issues] == ["authorization_missing"]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_eia_fetch_sends_key_but_never_persists_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "eia-fetch-key-sentinel"
    monkeypatch.setenv("EIA_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "eia_wti_pass.json").read_text())
    body["response"]["total"] = "1"

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["api_key"] == secret
        body["response"]["echo"] = {"api_key": secret}
        return httpx.Response(200, request=request, json=body)

    source = _eia_source()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await EIAAdapter(client).fetch(
            _provider("EIA_API_V2"),
            [(source, _dataset("Petroleum"))],
            mode="backfill",
        )

    _assert_secret_absent(results[0].request_url, secret)
    _assert_secret_absent(results[0].request_parameters, secret)
    _assert_secret_absent(results[0].raw_bytes, secret)
    assert "?" not in results[0].request_url
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_eia_seriesid_incremental_fetch_filters_locally_after_complete_pagination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import date, timedelta

    monkeypatch.setenv("EIA_API_KEY", "test-key")
    get_settings.cache_clear()
    recent_period = date.today() - timedelta(days=1)
    rows = [
        {
            "period": recent_period.isoformat(),
            "series": "RWTC",
            "value": "63.96",
            "units": "$/BBL",
        },
        {
            "period": "1986-01-03",
            "series": "RWTC",
            "value": "26.00",
            "units": "$/BBL",
        },
        {
            "period": "1986-01-02",
            "series": "RWTC",
            "value": "25.56",
            "units": "$/BBL",
        },
    ]
    offsets: list[int] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        assert "start" not in request.url.params
        assert "sort[0][column]" not in request.url.params
        assert "sort[0][direction]" not in request.url.params
        offset = int(request.url.params["offset"])
        length = int(request.url.params["length"])
        offsets.append(offset)
        return httpx.Response(
            200,
            request=request,
            json={"response": {"total": "3", "data": rows[offset : offset + length]}},
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        adapter = EIAAdapter(client)
        adapter.page_size = 2
        results = await adapter.fetch(
            _provider("EIA_API_V2"),
            [(_eia_source(), _dataset("Petroleum"))],
            mode="incremental",
        )

    assert offsets == [0, 2]
    assert [row.period_start for row in results[0].observations] == [recent_period]
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_eia_non_seriesid_incremental_fetch_rejects_rows_before_cutoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EIA_API_KEY", "test-key")
    get_settings.cache_clear()
    source = _eia_source(route="v2/petroleum/pri/spt/data")

    async def handler(request: httpx.Request) -> httpx.Response:
        assert "start" in request.url.params
        assert request.url.params["sort[0][column]"] == "period"
        return httpx.Response(
            200,
            request=request,
            json={
                "response": {
                    "total": "1",
                    "data": [{"period": "1986-01-02", "value": "25.56"}],
                }
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError, match="before requested cutoff"):
            await EIAAdapter(client).fetch(
                _provider("EIA_API_V2"),
                [(source, _dataset("Petroleum"))],
                mode="incremental",
            )
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_bea_fetch_sends_key_but_never_persists_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "bea-fetch-key-sentinel"
    monkeypatch.setenv("BEA_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "bea_pce_pass.json").read_text())

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["UserID"] == secret
        body["BEAAPI"]["Results"]["echo"] = {"UserID": secret}
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await BEAAdapter(client).fetch(
            _provider("BEA_API"),
            [(_bea_source(), _dataset("NIUnderlyingDetail"))],
            mode="backfill",
        )

    _assert_secret_absent(results[0].request_url, secret)
    _assert_secret_absent(results[0].request_parameters, secret)
    _assert_secret_absent(results[0].raw_bytes, secret)
    assert "?" not in results[0].request_url
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_bea_fetch_conflicting_identity_error_never_exposes_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "bea-conflicting-identity-key-sentinel"
    monkeypatch.setenv("BEA_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "bea_pce_pass.json").read_text())
    first = body["BEAAPI"]["Results"]["Data"][0]
    first["SeriesCode"] = secret
    conflicting = dict(first)
    conflicting["LineDescription"] = "Conflicting description"
    body["BEAAPI"]["Results"]["Data"].append(conflicting)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["UserID"] == secret
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ProviderDataError) as captured:
            await BEAAdapter(client).fetch(
                _provider("BEA_API"),
                [(_bea_source(), _dataset("NIUnderlyingDetail"))],
                mode="backfill",
            )

    assert secret not in str(captured.value)
    get_settings.cache_clear()


@pytest.mark.parametrize(
    ("transport", "http", "business", "identity", "http_status"),
    [
        (False, False, True, False, None),
        (True, False, True, False, 503),
        (True, True, False, True, 200),
    ],
)
def test_mapping_probe_result_rejects_causally_impossible_evidence(
    transport: bool,
    http: bool,
    business: bool,
    identity: bool,
    http_status: int | None,
) -> None:
    with pytest.raises(ValueError, match="causality"):
        MappingProbeResult(
            provider_code="TEST",
            source_series_id=1,
            provider_series_id=None,
            request_url="https://example.test/probe",
            http_reachable=transport,
            http_status=http_status,
            content_type="application/json",
            business_success=business,
            identity_match=identity,
            official_description="",
            response_sha256="",
            probed_at=datetime.now(UTC),
            authorization_available=True,
            production_ready=False,
            classification="BLOCKED",
            evidence=MappingProbeEvidence(
                transport,
                http,
                business,
                identity,
                True,
            ),
        )


@pytest.mark.asyncio
async def test_census_fetch_sends_key_but_never_persists_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "census-fetch-key-sentinel"
    monkeypatch.setenv("CENSUS_API_KEY", secret)
    get_settings.cache_clear()
    body = json.loads((FIXTURES / "census_retail_pass.json").read_text())

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["key"] == secret
        body.append([secret, "2025-02", "yes", "TOTAL", "1"])
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await CensusEITSAdapter(client).fetch(
            _provider("CENSUS_EITS_API"),
            [(_census_source(), _dataset("marts"))],
            mode="backfill",
        )

    _assert_secret_absent(results[0].request_url, secret)
    _assert_secret_absent(results[0].request_parameters, secret)
    _assert_secret_absent(results[0].raw_bytes, secret)
    assert "?" not in results[0].request_url
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_census_fetch_filters_full_pinned_identity_from_unfiltered_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from datetime import date

    monkeypatch.setenv("CENSUS_API_KEY", "test-key")
    get_settings.cache_clear()
    source = _census_source(
        start_year=1992,
        required_variables=[
            "data_type_code",
            "seasonally_adj",
            "category_code",
            "cell_value",
            "error_data",
            "time",
        ],
        dimensions={
            "data_type_code": "SM",
            "seasonally_adj": "yes",
            "category_code": "44X72",
            "error_data": "no",
            "for": "us:*",
        },
    )
    body = [
        [
            "cell_value",
            "time",
            "time_slot_date",
            "data_type_code",
            "seasonally_adj",
            "category_code",
            "error_data",
            "us",
        ],
        ["9.9", "2025-01", "2025-01-01", "SM", "yes", "441", "no", "1"],
        ["42.5", "2025-01", "2025-01-01", "SM", "yes", "44X72", "no", "1"],
        ["8.8", "2025-02", "2025-02-01", "IM", "yes", "44X72", "no", "1"],
        ["43.0", "2025-02", "2025-02-01", "SM", "yes", "44X72", "no", "1"],
    ]

    async def handler(request: httpx.Request) -> httpx.Response:
        assert set(request.url.params) == {"get", "time", "key", "for"}
        assert request.url.params["time"] == f"from 1992 to {date.today().year}"
        assert request.url.params["for"] == "us:*"
        requested = set(request.url.params["get"].split(","))
        assert "time" not in requested
        assert "time_slot_date" in requested
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await CensusEITSAdapter(client).fetch(
            _provider("CENSUS_EITS_API"),
            [(source, _dataset("marts"))],
            mode="backfill",
        )

    assert [
        (row.period_start.isoformat(), str(row.value)) for row in results[0].observations
    ] == [("2025-01-01", "42.5"), ("2025-02-01", "43.0")]
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_type", "environment_name", "source", "dataset"),
    [
        (EIAAdapter, "EIA_API_KEY", _eia_source(), _dataset("Petroleum")),
        (BEAAdapter, "BEA_API_KEY", _bea_source(), _dataset("NIUnderlyingDetail")),
        (CensusEITSAdapter, "CENSUS_API_KEY", _census_source(), _dataset("marts")),
    ],
)
async def test_fetch_http_errors_never_expose_key(
    monkeypatch: pytest.MonkeyPatch,
    adapter_type: type[EIAAdapter] | type[BEAAdapter] | type[CensusEITSAdapter],
    environment_name: str,
    source: SimpleNamespace,
    dataset: SimpleNamespace,
) -> None:
    secret = "fetch-error-key-sentinel"
    monkeypatch.setenv(environment_name, secret)
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        assert secret in str(request.url)
        return httpx.Response(
            500,
            request=request,
            headers={"X-Api-Key": secret, "X-Echo": secret},
            content=secret.encode(),
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.HTTPStatusError) as captured:
            await adapter_type(client).fetch(
                _provider(adapter_type.code), [(source, dataset)], mode="backfill"
            )

    assert secret not in str(captured.value)
    assert "?" not in str(captured.value.request.url)
    assert secret not in str(captured.value.response.headers)
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("adapter_type", "environment_name", "source", "dataset"),
    [
        (EIAAdapter, "EIA_API_KEY", _eia_source(), _dataset("Petroleum")),
        (BEAAdapter, "BEA_API_KEY", _bea_source(), _dataset("NIUnderlyingDetail")),
        (CensusEITSAdapter, "CENSUS_API_KEY", _census_source(), _dataset("marts")),
    ],
)
async def test_fetch_transport_errors_never_expose_key(
    monkeypatch: pytest.MonkeyPatch,
    adapter_type: type[EIAAdapter] | type[BEAAdapter] | type[CensusEITSAdapter],
    environment_name: str,
    source: SimpleNamespace,
    dataset: SimpleNamespace,
) -> None:
    secret = "fetch-transport-key-sentinel"
    monkeypatch.setenv(environment_name, secret)
    get_settings.cache_clear()

    async def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(secret, request=request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(httpx.TransportError) as captured:
            await adapter_type(client).fetch(
                _provider(adapter_type.code), [(source, dataset)], mode="backfill"
            )

    assert secret not in str(captured.value)
    assert captured.value.request is not None
    assert "?" not in str(captured.value.request.url)
    get_settings.cache_clear()


@pytest.mark.asyncio
@pytest.mark.parametrize("provider_code", ["EIA_API_V2", "BEA_API", "CENSUS_EITS_API"])
async def test_fetch_business_errors_never_expose_key(
    monkeypatch: pytest.MonkeyPatch,
    provider_code: str,
) -> None:
    secret = "fetch-business-key-sentinel"
    environment_by_provider = {
        "EIA_API_V2": "EIA_API_KEY",
        "BEA_API": "BEA_API_KEY",
        "CENSUS_EITS_API": "CENSUS_API_KEY",
    }
    monkeypatch.setenv(environment_by_provider[provider_code], secret)
    get_settings.cache_clear()
    if provider_code == "EIA_API_V2":
        adapter_type = EIAAdapter
        source = _eia_source()
        dataset = _dataset("Petroleum")
        body: object = {"error": {"message": secret}}
    elif provider_code == "BEA_API":
        adapter_type = BEAAdapter
        source = _bea_source()
        dataset = _dataset("NIUnderlyingDetail")
        body = {"BEAAPI": {"Error": {"APIErrorDescription": secret}}}
    else:
        adapter_type = CensusEITSAdapter
        source = _census_source()
        dataset = _dataset("marts")
        body = [
            ["cell_value", "time", "seasonally_adj", "category_code", "us"],
            ["42.5", "2025-01", secret, "TOTAL", "1"],
        ]

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, request=request, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Exception) as captured:
            await adapter_type(client).fetch(
                _provider(provider_code), [(source, dataset)], mode="backfill"
            )

    assert secret not in str(captured.value)
    get_settings.cache_clear()
