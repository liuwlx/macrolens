from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
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
    normalize_label,
    parse_decimal,
    period_end,
)


class BEAAdapter(ProviderAdapter):
    code = "BEA_API"
    endpoint = "https://apps.bea.gov/api/data"

    async def probe(
        self,
        provider: Provider,
        source: SourceSeries,
        dataset: Dataset,
    ) -> MappingProbeResult:
        settings = get_settings()
        authorized = bool(settings.bea_api_key)
        probed_at = datetime.now(UTC)
        provider_series_id = str(source.provider_series_id) if source.provider_series_id else None
        locator = source.source_locator
        pinned = {
            "table_name": str(locator.get("table_name") or ""),
            "frequency": str(locator.get("frequency") or ""),
            "series_code": str(locator.get("series_code") or ""),
            "line_number": str(locator.get("line_number") or ""),
            "line_description": str(locator.get("line_description") or ""),
        }
        missing = [name for name, value in pinned.items() if not value.strip()]
        if missing:
            return _build_mapping_probe_result(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=provider_series_id,
                request_url=self.endpoint,
                http_status=None,
                content_type="",
                official_description="",
                response_sha256="",
                probed_at=probed_at,
                evidence=MappingProbeEvidence(False, False, False, False, authorized),
                issues=tuple(
                    MappingProbeIssue(
                        "configuration",
                        f"{name}_missing",
                        f"BEA {name} must be pinned before probing",
                    )
                    for name in missing
                ),
            )
        params: dict[str, Any] = {
            "method": "GetData",
            "DataSetName": dataset.code,
            "TableName": pinned["table_name"],
            "Frequency": pinned["frequency"],
            "Year": str(locator.get("probe_year") or date.today().year),
            "ResultFormat": "JSON",
        }
        if settings.bea_api_key:
            params["UserID"] = settings.bea_api_key
        try:
            response = await self.client.get(self.endpoint, params=params)
        except httpx.TransportError:
            return _build_mapping_probe_result(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=provider_series_id,
                request_url=self.endpoint,
                http_status=None,
                content_type="",
                official_description="",
                response_sha256="",
                probed_at=probed_at,
                evidence=MappingProbeEvidence(False, False, False, False, authorized),
                issues=(
                    MappingProbeIssue(
                        "transport", "transport_error", "BEA request was unreachable"
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
                request_url=self.endpoint,
                http_status=response.status_code,
                content_type=content_type,
                official_description="",
                response_sha256=digest,
                probed_at=probed_at,
                evidence=MappingProbeEvidence(True, False, False, False, authorized),
                issues=(
                    MappingProbeIssue(
                        "http", "http_status", f"BEA returned HTTP {response.status_code}"
                    ),
                ),
            )
        try:
            secrets = (settings.bea_api_key,) if settings.bea_api_key else ()
            payload = _redact_sensitive_data(response.json(), secrets=secrets)
        except ValueError:
            payload = None
        errors = self._business_errors(payload)
        data_rows = self._data_rows(payload)
        if errors or data_rows is None:
            return _build_mapping_probe_result(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=provider_series_id,
                request_url=self.endpoint,
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
                        "BEA response reported a business error"
                        if errors
                        else "BEA response did not contain a Data list",
                    ),
                ),
            )

        expected_description = self._normalize_whitespace(pinned["line_description"])
        identity_rows = [
            row
            for row in data_rows
            if isinstance(row, dict)
            and str(row.get("SeriesCode") or "") == pinned["series_code"]
            and str(row.get("LineNumber") or "") == pinned["line_number"]
        ]
        identities = {
            (
                str(row.get("SeriesCode") or ""),
                str(row.get("LineNumber") or ""),
                self._normalize_whitespace(str(row.get("LineDescription") or "")),
            )
            for row in identity_rows
        }
        issue_specs: list[tuple[str, str]] = []
        if len(identities) != 1:
            issue_specs.append(
                ("identity_not_unique", "BEA fixed identity did not resolve uniquely")
            )
        elif next(iter(identities))[2] != expected_description:
            issue_specs.append(
                (
                    "line_description_drift",
                    "BEA LineDescription does not exactly match after whitespace normalization",
                )
            )
        first_row = identity_rows[0] if identity_rows else {}
        if not identity_rows or any(
            self._parse_period(str(row.get("TimePeriod") or "")) is None for row in identity_rows
        ):
            issue_specs.append(
                ("time_period_invalid", "BEA TimePeriod must be present and parseable")
            )
        if not identity_rows or any(
            parse_decimal(row.get("DataValue")) is None for row in identity_rows
        ):
            issue_specs.append(
                ("data_value_invalid", "BEA DataValue must be present and parseable")
            )
        for locator_name, response_name in (
            ("metric_name", "METRIC_NAME"),
            ("cl_unit", "CL_UNIT"),
            ("unit_mult", "UNIT_MULT"),
        ):
            expected = locator.get(locator_name)
            if expected is not None and (
                not identity_rows
                or any(
                    self._string_value(row.get(response_name)) != str(expected)
                    for row in identity_rows
                )
            ):
                issue_specs.append(
                    (
                        f"{locator_name}_drift",
                        f"BEA {response_name} does not match the pinned value",
                    )
                )
        issues = [MappingProbeIssue("identity", code, message) for code, message in issue_specs]
        if not authorized:
            issues.append(
                MappingProbeIssue(
                    "authorization",
                    "authorization_missing",
                    "BEA API authorization is unavailable",
                )
            )
        details = {
            "table_name": pinned["table_name"],
            "frequency": pinned["frequency"],
            "series_code": str(first_row.get("SeriesCode") or ""),
            "line_number": str(first_row.get("LineNumber") or ""),
            "line_description": self._normalize_whitespace(
                str(first_row.get("LineDescription") or "")
            ),
            "time_period": str(first_row.get("TimePeriod") or ""),
            "metric_name": self._string_value(first_row.get("METRIC_NAME")),
            "cl_unit": self._string_value(first_row.get("CL_UNIT")),
            "unit_mult": self._string_value(first_row.get("UNIT_MULT")),
        }
        return _build_mapping_probe_result(
            provider_code=provider.code,
            source_series_id=source.id,
            provider_series_id=provider_series_id,
            request_url=self.endpoint,
            http_status=response.status_code,
            content_type=content_type,
            official_description=details["line_description"],
            response_sha256=digest,
            probed_at=probed_at,
            evidence=MappingProbeEvidence(
                True,
                True,
                True,
                not issue_specs,
                authorized,
                details,
            ),
            issues=tuple(issues),
        )

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return " ".join(value.split())

    @staticmethod
    def _string_value(value: Any) -> str:
        return "" if value is None else str(value)

    @staticmethod
    def _business_errors(payload: Any) -> list[Any]:
        if not isinstance(payload, dict):
            return []
        bea_api = payload.get("BEAAPI")
        if not isinstance(bea_api, dict):
            return []
        errors: list[Any] = []
        if bea_api.get("Error"):
            errors.append(bea_api["Error"])
        results = bea_api.get("Results")
        if isinstance(results, dict) and results.get("Error"):
            errors.append(results["Error"])
        elif isinstance(results, list):
            errors.extend(
                item["Error"] for item in results if isinstance(item, dict) and item.get("Error")
            )
        return errors

    @staticmethod
    def _data_rows(payload: Any) -> list[dict[str, Any]] | None:
        if not isinstance(payload, dict):
            return None
        bea_api = payload.get("BEAAPI")
        if not isinstance(bea_api, dict):
            return None
        results = bea_api.get("Results")
        if isinstance(results, dict):
            rows = results.get("Data")
            return rows if isinstance(rows, list) else None
        if isinstance(results, list):
            data_items = [item.get("Data") for item in results if isinstance(item, dict)]
            rows = next((item for item in data_items if isinstance(item, list)), None)
            return rows
        return None

    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        settings = get_settings()
        if not settings.bea_api_key:
            raise RuntimeError("BEA_API_KEY is required")
        grouped: dict[tuple[int, str, str], list[SourceSeries]] = defaultdict(list)
        dataset_by_id: dict[int, Dataset] = {}
        for source, dataset in mappings:
            table_name = str(
                source.source_locator.get("table_name")
                or source.source_locator.get("TableName")
                or ""
            )
            frequency = str(source.source_locator.get("frequency") or self._frequency_code(source))
            if not table_name:
                raise ProviderDataError(f"BEA mapping {source.id} has no table_name")
            grouped[(dataset.id, table_name, frequency)].append(source)
            dataset_by_id[dataset.id] = dataset

        results: list[ProviderFetchResult] = []
        for (dataset_id, table_name, frequency), sources in grouped.items():
            dataset = dataset_by_id[dataset_id]
            params = {
                "UserID": settings.bea_api_key,
                "method": "GetData",
                "DataSetName": dataset.code,
                "TableName": table_name,
                "Frequency": frequency,
                "Year": (
                    "ALL"
                    if mode in {"backfill", "vintage_backfill"}
                    else ",".join(
                        str(year) for year in range(date.today().year - 5, date.today().year + 1)
                    )
                ),
                "ResultFormat": "JSON",
            }
            try:
                response = await self.client.get(self.endpoint, params=params)
            except httpx.TransportError:
                raise _sanitized_transport_error(
                    provider_code=self.code, request_url=self.endpoint
                ) from None
            _raise_for_status_safely(
                response,
                provider_code=self.code,
                request_url=self.endpoint,
                secrets=(settings.bea_api_key,),
            )
            payload = _redact_sensitive_data(response.json(), secrets=(settings.bea_api_key,))
            errors = self._business_errors(payload)
            if errors:
                raise ProviderDataError("BEA request failed with a business error")
            results_payload = payload.get("BEAAPI", {}).get("Results", {})
            if isinstance(results_payload, list):
                # Some BEA methods wrap Results in a list. GetData normally returns a mapping.
                results_payload = next(
                    (item for item in results_payload if isinstance(item, dict)), {}
                )
            data_rows = results_payload.get("Data", []) if isinstance(results_payload, dict) else []
            if not isinstance(data_rows, list):
                raise ProviderDataError("BEA response did not contain a Data list")

            identities = self._resolve_identities(sources, data_rows)
            fetched_at = datetime.now(UTC)
            observations: list[NormalizedObservation] = []
            for source in sources:
                identity = identities[source.id]
                platform_unit_scale = self._platform_unit_scale(source)
                for row in data_rows:
                    if not isinstance(row, dict):
                        raise ProviderDataError("BEA Data contained a non-object row")
                    if not self._row_matches(row, identity):
                        continue
                    period_text = str(row.get("TimePeriod", ""))
                    period = self._parse_period(period_text)
                    if period is None:
                        raise ProviderDataError(
                            f"BEA mapping {source.id} returned an invalid TimePeriod"
                        )
                    value = parse_decimal(row.get("DataValue"))
                    flags: list[str] = []
                    if value is None:
                        flags.append("missing_value")
                    elif platform_unit_scale is not None:
                        value *= platform_unit_scale
                        flags.append(f"scaled_to_platform_unit:{platform_unit_scale}")
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
            observations = deduplicate_observations(observations)
            raw_bundle = json.dumps(
                {
                    "provider": self.code,
                    "resolved_identities": identities,
                    "response": _redact_sensitive_data(payload, secrets=(settings.bea_api_key,)),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=dataset,
                    request_url=self.endpoint,
                    request_parameters=_redact_sensitive_data(
                        params, secrets=(settings.bea_api_key,)
                    ),
                    content_type=response.headers.get("content-type", "application/json"),
                    raw_bytes=raw_bundle,
                    observations=observations,
                )
            )
        return results

    @staticmethod
    def _platform_unit_scale(source: SourceSeries) -> Decimal | None:
        raw_scale = source.source_locator.get("value_scale_to_platform_unit")
        if raw_scale is None:
            return None
        try:
            scale = Decimal(str(raw_scale))
        except InvalidOperation as exc:
            raise ProviderDataError(
                f"BEA mapping {source.id} has invalid value_scale_to_platform_unit"
            ) from exc
        if not scale.is_finite() or scale <= 0:
            raise ProviderDataError(
                f"BEA mapping {source.id} value_scale_to_platform_unit must be positive"
            )
        return scale

    @staticmethod
    def _frequency_code(source: SourceSeries) -> str:
        return {
            "monthly": "M",
            "quarterly": "Q",
            "annual": "A",
        }.get(source.source_frequency or "", "M")

    @staticmethod
    def _parse_period(period_text: str) -> date | None:
        text = period_text.strip().upper()
        if "M" in text:
            year, month = text.split("M", 1)
            if year.isdigit() and month.isdigit() and 1 <= int(month) <= 12:
                return date(int(year), int(month), 1)
        if "Q" in text:
            year, quarter = text.split("Q", 1)
            if year.isdigit() and quarter.isdigit() and 1 <= int(quarter) <= 4:
                return date(int(year), (int(quarter) - 1) * 3 + 1, 1)
        if text.isdigit() and len(text) == 4:
            return date(int(text), 1, 1)
        return None

    @classmethod
    def _resolve_identities(
        cls, sources: list[SourceSeries], rows: list[dict[str, Any]]
    ) -> dict[int, dict[str, str]]:
        metadata: dict[tuple[str, str], str] = {}
        for row in rows:
            series_code = str(row.get("SeriesCode") or "")
            line_number = str(row.get("LineNumber") or "")
            description = str(row.get("LineDescription") or "")
            if series_code or line_number:
                key = (series_code, line_number)
                previous = metadata.get(key)
                if previous is not None and normalize_label(previous) != normalize_label(
                    description
                ):
                    raise ProviderDataError(f"BEA row identity {key} has conflicting descriptions")
                metadata[key] = description

        identities: dict[int, dict[str, str]] = {}
        for source in sources:
            locator = source.source_locator
            explicit_series = str(locator.get("series_code") or "")
            explicit_line = str(locator.get("line_number") or "")
            if explicit_series or explicit_line:
                matches = [
                    (series_code, line_number, description)
                    for (series_code, line_number), description in metadata.items()
                    if (not explicit_series or series_code == explicit_series)
                    and (not explicit_line or line_number == explicit_line)
                ]
            else:
                raw_aliases = (
                    locator.get("line_aliases") or locator.get("description_aliases") or []
                )
                if isinstance(raw_aliases, str):
                    raw_aliases = [raw_aliases]
                aliases = [
                    str(value)
                    for value in [
                        locator.get("line_match"),
                        locator.get("target_description_en"),
                        *raw_aliases,
                        source.source_title,
                    ]
                    if value
                ]
                normalized_aliases = {
                    normalize_label(alias) for alias in aliases if normalize_label(alias)
                }
                exact = [
                    (series_code, line_number, description)
                    for (series_code, line_number), description in metadata.items()
                    if normalize_label(description) in normalized_aliases
                ]
                matches = exact
                if not matches and bool(locator.get("allow_contains_match", False)):
                    matches = [
                        (series_code, line_number, description)
                        for (series_code, line_number), description in metadata.items()
                        if any(
                            alias in normalize_label(description)
                            or normalize_label(description) in alias
                            for alias in normalized_aliases
                        )
                    ]
            unique = {
                (series_code, line_number, description)
                for series_code, line_number, description in matches
            }
            if len(unique) != 1:
                raise ProviderDataError(
                    f"BEA mapping {source.id} must resolve to exactly one row; "
                    f"found {len(unique)} candidates"
                )
            series_code, line_number, description = unique.pop()
            identities[source.id] = {
                "series_code": series_code,
                "line_number": line_number,
                "line_description": description,
            }
        return identities

    @staticmethod
    def _row_matches(row: dict[str, Any], identity: dict[str, str]) -> bool:
        return (
            str(row.get("SeriesCode") or "") == identity["series_code"]
            and str(row.get("LineNumber") or "") == identity["line_number"]
        )
