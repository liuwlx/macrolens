from __future__ import annotations

import json
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any

import httpx

from macrolens_api.config import get_settings
from macrolens_api.models import Dataset, Provider, SourceSeries

from .base import (
    MappingProbeEvidence,
    MappingProbeIssue,
    MappingProbeResult,
    NormalizedObservation,
    ProviderAdapter,
    ProviderDataError,
    ProviderFetchResult,
    _build_mapping_probe_result,
    _raise_for_status_safely,
    _redact_sensitive_data,
    _sanitized_transport_error,
    deduplicate_observations,
    parse_decimal,
    period_end,
)


class CensusEITSAdapter(ProviderAdapter):
    """Census Economic Indicators Time Series adapter.

    Census datasets are multidimensional. A source mapping is executable only after every
    required dimension has been pinned to an approved code. This prevents, for example,
    publishing an unadjusted subcategory under a seasonally adjusted headline label.
    """

    code = "CENSUS_EITS_API"

    async def probe(
        self,
        provider: Provider,
        source: SourceSeries,
        dataset: Dataset,
    ) -> MappingProbeResult:
        del dataset
        settings = get_settings()
        authorized = bool(settings.census_api_key)
        probed_at = datetime.now(UTC)
        provider_series_id = str(source.provider_series_id) if source.provider_series_id else None
        locator = source.source_locator
        path = str(locator.get("path") or "").strip("/")
        request_url = f"https://api.census.gov/data/{path}"
        value_field = str(locator.get("value_field") or "")
        time_field = str(locator.get("time_field") or "")
        required_variables = locator.get("required_variables")
        dimensions = locator.get("dimensions")
        configuration_issues: list[MappingProbeIssue] = []
        if locator.get("resolve_dimensions_from_dictionary"):
            configuration_issues.append(
                MappingProbeIssue(
                    "configuration",
                    "dimensions_unresolved",
                    "Census dimensions must be resolved from the official dictionary",
                )
            )
        for name, value in (
            ("path", path),
            ("value_field", value_field),
            ("time_field", time_field),
        ):
            if not value:
                configuration_issues.append(
                    MappingProbeIssue(
                        "configuration",
                        f"{name}_missing",
                        f"Census {name} must be pinned before probing",
                    )
                )
        if not isinstance(required_variables, list) or not required_variables:
            configuration_issues.append(
                MappingProbeIssue(
                    "configuration",
                    "required_variables_missing",
                    "Census required_variables must be a non-empty pinned list",
                )
            )
        if (
            not isinstance(dimensions, dict)
            or not dimensions
            or any(value is None or str(value) == "" for value in dimensions.values())
        ):
            configuration_issues.append(
                MappingProbeIssue(
                    "configuration",
                    "dimensions_incomplete",
                    "Census dimensions must be complete before probing",
                )
            )
        if not isinstance(dimensions, dict) or dimensions.get("for") != "us:*":
            configuration_issues.append(
                MappingProbeIssue(
                    "configuration",
                    "country_predicate_invalid",
                    "Census dimensions['for'] must be pinned to us:* before probing",
                )
            )
        probe_period = str(locator.get("probe_period") or date.today().strftime("%Y-%m"))
        if self._parse_period(probe_period) is None or len(probe_period) != 7:
            configuration_issues.append(
                MappingProbeIssue(
                    "configuration",
                    "probe_period_invalid",
                    "Census probe_period must identify one YYYY-MM month",
                )
            )
        if configuration_issues:
            return _build_mapping_probe_result(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=provider_series_id,
                request_url=request_url,
                http_status=None,
                content_type="",
                official_description="",
                response_sha256="",
                probed_at=probed_at,
                evidence=MappingProbeEvidence(False, False, False, False, authorized),
                issues=tuple(configuration_issues),
            )

        assert isinstance(required_variables, list)
        assert isinstance(dimensions, dict)
        get_fields = [
            field
            for field in dict.fromkeys(
                [
                    value_field,
                    time_field,
                    *[str(item) for item in required_variables],
                    *[str(key) for key in dimensions if key != "for"],
                ]
            )
            if field != "time"
        ]
        params: dict[str, Any] = {
            "get": ",".join(get_fields),
            "time": probe_period,
            "for": str(dimensions["for"]),
        }
        if settings.census_api_key:
            params["key"] = settings.census_api_key
        try:
            response = await self.client.get(request_url, params=params)
        except httpx.TransportError:
            return _build_mapping_probe_result(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=provider_series_id,
                request_url=request_url,
                http_status=None,
                content_type="",
                official_description="",
                response_sha256="",
                probed_at=probed_at,
                evidence=MappingProbeEvidence(False, False, False, False, authorized),
                issues=(
                    MappingProbeIssue(
                        "transport",
                        "transport_error",
                        "Census request was unreachable",
                    ),
                ),
            )
        raw = response.content
        digest = sha256(raw).hexdigest()
        content_type = response.headers.get("content-type", "application/json")
        if not 200 <= response.status_code < 300:
            return _build_mapping_probe_result(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=provider_series_id,
                request_url=request_url,
                http_status=response.status_code,
                content_type=content_type,
                official_description="",
                response_sha256=digest,
                probed_at=probed_at,
                evidence=MappingProbeEvidence(True, False, False, False, authorized),
                issues=(
                    MappingProbeIssue(
                        "http",
                        "http_status",
                        f"Census returned HTTP {response.status_code}",
                    ),
                ),
            )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        payload = _redact_sensitive_data(payload, secrets=(settings.census_api_key or "",))
        if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
            return _build_mapping_probe_result(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=provider_series_id,
                request_url=request_url,
                http_status=response.status_code,
                content_type=content_type,
                official_description="",
                response_sha256=digest,
                probed_at=probed_at,
                evidence=MappingProbeEvidence(True, True, False, False, authorized),
                issues=(
                    MappingProbeIssue(
                        "business",
                        "business_error",
                        "Census response was not a matrix payload",
                    ),
                ),
            )

        headers = [str(item) for item in payload[0]]
        raw_rows = payload[1:]
        identity_issues: list[MappingProbeIssue] = []
        required_headers = {
            value_field,
            time_field,
            *[str(item) for item in required_variables],
            *[str(key) for key in dimensions if key != "for"],
        }
        for_value = str(dimensions.get("for") or "")
        geography_name = for_value.split(":", 1)[0] if for_value else ""
        predicate = for_value.split(":", 1)[1] if ":" in for_value else ""
        expected_geography = (
            "1"
            if geography_name == "us" and predicate == "*"
            else predicate
            if predicate != "*"
            else None
        )
        expected_headers = required_headers | ({geography_name} if geography_name else set())
        if len(headers) != len(set(headers)) or set(headers) != expected_headers:
            identity_issues.append(
                MappingProbeIssue(
                    "identity",
                    "headers_mismatch",
                    "Census headers do not exactly cover the pinned fields",
                )
            )
        matching_rows: list[dict[str, Any]] = []
        malformed_row = False
        for raw_row in raw_rows:
            if not isinstance(raw_row, list) or len(raw_row) != len(headers):
                malformed_row = True
                continue
            candidate = dict(zip(headers, raw_row, strict=True))
            geography_matches = geography_name in candidate and bool(
                str(candidate.get(geography_name) or "")
            )
            if expected_geography is not None:
                geography_matches = (
                    geography_matches
                    and str(candidate.get(geography_name)) == expected_geography
                )
            if self._dimensions_match(candidate, dimensions) and geography_matches:
                matching_rows.append(candidate)
        if malformed_row:
            identity_issues.append(
                MappingProbeIssue(
                    "identity",
                    "row_width_mismatch",
                    "Census row width does not match the headers",
                )
            )
        if len(matching_rows) != 1:
            identity_issues.append(
                MappingProbeIssue(
                    "identity",
                    "row_count_invalid",
                    "Census probe must match exactly one row after pinned-dimension filtering",
                )
            )
            row: dict[str, Any] = {}
        else:
            row = matching_rows[0]
        response_dimensions = {
            str(key): str(row.get(str(key)) or "") for key in dimensions if key != "for"
        }
        expected_dimensions = {
            str(key): str(value) for key, value in dimensions.items() if key != "for"
        }
        if response_dimensions != expected_dimensions:
            identity_issues.append(
                MappingProbeIssue(
                    "identity",
                    "dimensions_drift",
                    "Census response dimensions do not match the pinned identity",
                )
            )
        geography: dict[str, str] = {}
        if for_value:
            geography_value = str(row.get(geography_name) or "")
            if geography_name in row:
                geography[geography_name] = geography_value
            if not geography_value or (
                expected_geography is not None and geography_value != expected_geography
            ):
                identity_issues.append(
                    MappingProbeIssue(
                        "identity",
                        "geography_drift",
                        "Census response geography does not match the request predicate",
                    )
                )
        if str(row.get(time_field) or "") != probe_period:
            identity_issues.append(
                MappingProbeIssue(
                    "identity",
                    "time_drift",
                    "Census response time does not match the requested month",
                )
            )
        if value_field not in row or parse_decimal(row.get(value_field)) is None:
            identity_issues.append(
                MappingProbeIssue(
                    "identity",
                    "value_invalid",
                    "Census value field must be present and parseable",
                )
            )
        if not authorized:
            identity_issues.append(
                MappingProbeIssue(
                    "authorization",
                    "authorization_missing",
                    "Census API authorization is unavailable",
                )
            )
        details = {
            "headers": headers,
            "dimensions": response_dimensions,
            "geography": geography,
            "value_field": value_field,
            "value": str(row.get(value_field) or ""),
            "time": str(row.get(time_field) or ""),
        }
        return _build_mapping_probe_result(
            provider_code=provider.code,
            source_series_id=source.id,
            provider_series_id=provider_series_id,
            request_url=request_url,
            http_status=response.status_code,
            content_type=content_type,
            official_description="",
            response_sha256=digest,
            probed_at=probed_at,
            evidence=MappingProbeEvidence(
                True,
                True,
                True,
                not any(issue.stage == "identity" for issue in identity_issues),
                authorized,
                details,
            ),
            issues=tuple(identity_issues),
        )

    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        settings = get_settings()
        if not settings.census_api_key:
            raise RuntimeError("CENSUS_API_KEY is required")
        results: list[ProviderFetchResult] = []
        current_year = date.today().year
        for source, dataset in mappings:
            locator = source.source_locator
            if locator.get("resolve_dimensions_from_dictionary"):
                raise ProviderDataError(
                    f"Census mapping {source.id} is unresolved; approve official "
                    "dictionary dimensions first"
                )
            value_field = str(locator.get("value_field") or "cell_value")
            time_field = str(locator.get("time_field") or "time")
            dimensions = locator.get("dimensions") or {}
            if not isinstance(dimensions, dict) or not dimensions:
                raise ProviderDataError(f"Census mapping {source.id} has no pinned dimensions")

            required_variables = locator.get("required_variables") or []
            if not isinstance(required_variables, list):
                raise ProviderDataError(
                    f"Census mapping {source.id} required_variables must be a list"
                )
            get_fields = [
                field
                for field in dict.fromkeys(
                    [
                        value_field,
                        time_field,
                        "time_slot_date",
                        *required_variables,
                        *[key for key in dimensions if key != "for"],
                    ]
                )
                if field != "time"
            ]
            path = str(locator.get("path") or f"timeseries/eits/{dataset.code}").strip("/")
            url = f"https://api.census.gov/data/{path}"
            start_value = str(locator.get("start") or (locator.get("start_year") or 1990))
            if mode not in {"backfill", "vintage_backfill"}:
                start_value = str(current_year - 5)
            end_value = str(locator.get("end") or current_year)
            time_value = f"from {start_value} to {end_value}"
            params: dict[str, Any] = {
                "get": ",".join(get_fields),
                "time": time_value,
                "key": settings.census_api_key,
            }
            if "for" in dimensions:
                params["for"] = str(dimensions["for"])

            try:
                response = await self.client.get(url, params=params)
            except httpx.TransportError:
                raise _sanitized_transport_error(provider_code=self.code, request_url=url) from None
            _raise_for_status_safely(
                response,
                provider_code=self.code,
                request_url=url,
                secrets=(settings.census_api_key,),
            )
            payload = response.json()
            fetched_at = datetime.now(UTC)
            observations: list[NormalizedObservation] = []
            if not isinstance(payload, list) or not payload:
                raise ProviderDataError(
                    f"Census mapping {source.id} returned an invalid matrix payload"
                )
            headers = [str(item) for item in payload[0]]
            required_headers = {value_field}
            if (
                time_field not in headers
                and "time" not in headers
                and "time_slot_date" not in headers
            ):
                required_headers.add(time_field)
            required_headers.update(
                str(key)
                for key, expected in dimensions.items()
                if key != "for" and expected not in {None, ""}
            )
            missing_headers = required_headers - set(headers)
            if missing_headers:
                raise ProviderDataError(
                    f"Census mapping {source.id} response is missing fields "
                    f"{sorted(missing_headers)}"
                )
            seen_periods: set[date] = set()
            for raw_row in payload[1:]:
                if not isinstance(raw_row, list):
                    raise ProviderDataError(
                        f"Census mapping {source.id} returned a non-list data row"
                    )
                if len(raw_row) != len(headers):
                    raise ProviderDataError(
                        f"Census mapping {source.id} returned {len(raw_row)} cells for "
                        f"{len(headers)} headers"
                    )
                row = dict(zip(headers, raw_row, strict=True))
                if not self._dimensions_match(row, dimensions):
                    continue
                time_text = str(
                    row.get(time_field) or row.get("time_slot_date") or row.get("time") or ""
                )
                period = self._parse_period(time_text)
                if period is None:
                    raise ProviderDataError(
                        f"Census mapping {source.id} returned an invalid time value"
                    )
                if period in seen_periods:
                    raise ProviderDataError(
                        f"Census mapping {source.id} returned duplicate period {period}; "
                        "pin every remaining dimension before enabling the mapping"
                    )
                seen_periods.add(period)
                value = parse_decimal(row.get(value_field))
                flags = ["missing_value"] if value is None else []
                observations.append(
                    NormalizedObservation(
                        source_series_id=source.id,
                        period_start=period,
                        period_end=period_end(period, source.source_frequency or "monthly"),
                        value=value,
                        status="missing" if value is None else "normal",
                        vintage_at=fetched_at,
                        source_updated_at=fetched_at,
                        quality_flags=flags,
                    )
                )
            if not observations:
                raise ProviderDataError(
                    f"Census mapping {source.id} returned no rows matching pinned dimensions"
                )
            observations = deduplicate_observations(observations)
            raw_bundle = json.dumps(
                {
                    "provider": self.code,
                    "request": _redact_sensitive_data(params, secrets=(settings.census_api_key,)),
                    "response": _redact_sensitive_data(payload, secrets=(settings.census_api_key,)),
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=dataset,
                    request_url=url,
                    request_parameters=_redact_sensitive_data(
                        params, secrets=(settings.census_api_key,)
                    ),
                    content_type=response.headers.get("content-type", "application/json"),
                    raw_bytes=raw_bundle,
                    observations=observations,
                )
            )
        return results

    @staticmethod
    def _dimensions_match(row: dict[str, Any], dimensions: dict[str, Any]) -> bool:
        for key, expected in dimensions.items():
            if key == "for":
                geography_name, separator, predicate = str(expected).partition(":")
                if not separator or geography_name not in row:
                    return False
                actual = str(row.get(geography_name) or "")
                if not actual:
                    return False
                if geography_name == "us" and predicate == "*":
                    if actual != "1":
                        return False
                elif predicate != "*" and actual != predicate:
                    return False
                continue
            if expected is None or expected == "":
                continue
            if key not in row:
                return False
            if str(row.get(key)) != str(expected):
                return False
        return True

    @staticmethod
    def _parse_period(value: str) -> date | None:
        text = value.strip().upper()
        if not text:
            return None
        if "-Q" in text:
            year, quarter = text.split("-Q", 1)
            if year.isdigit() and quarter.isdigit() and 1 <= int(quarter) <= 4:
                return date(int(year), (int(quarter) - 1) * 3 + 1, 1)
        if len(text) >= 7 and text[4] == "-" and text[5:7].isdigit():
            try:
                return date.fromisoformat(f"{text[:7]}-01")
            except ValueError:
                pass
        try:
            parsed = date.fromisoformat(text[:10])
            return parsed.replace(day=1)
        except ValueError:
            pass
        if text.isdigit() and len(text) == 4:
            return date(int(text), 1, 1)
        return None
