from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
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
    build_mapping_probe_result,
    deduplicate_observations,
    parse_decimal,
    period_end,
)


class EIAAdapter(ProviderAdapter):
    code = "EIA_API_V2"
    page_size = 5000
    max_pages = 1000

    async def probe(
        self,
        provider: Provider,
        source: SourceSeries,
        dataset: Dataset,
    ) -> MappingProbeResult:
        del dataset
        settings = get_settings()
        authorized = bool(settings.eia_api_key)
        probed_at = datetime.now(UTC)
        provider_series_id = str(source.provider_series_id) if source.provider_series_id else None
        expected_route = f"v2/seriesid/{provider_series_id}" if provider_series_id else None
        route = str(source.source_locator.get("route") or "").strip("/")
        request_url = self._route_url(route or expected_route or "", False)
        configuration_issues: list[MappingProbeIssue] = []
        if not provider_series_id:
            configuration_issues.append(
                MappingProbeIssue(
                    "configuration",
                    "provider_series_id_missing",
                    "EIA provider_series_id must be pinned before probing",
                )
            )
        if route != expected_route:
            configuration_issues.append(
                MappingProbeIssue(
                    "configuration",
                    "route_not_pinned",
                    "EIA route must exactly match the pinned v2 series route",
                )
            )
        expected_first_period = str(source.source_locator.get("expected_first_period") or "")
        if not expected_first_period:
            configuration_issues.append(
                MappingProbeIssue(
                    "configuration",
                    "expected_first_period_missing",
                    "EIA expected_first_period must be pinned before probing",
                )
            )
        if configuration_issues:
            return build_mapping_probe_result(
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

        params: dict[str, Any] = {
            "length": 1,
            "sort[0][column]": "period",
            "sort[0][direction]": "asc",
        }
        if settings.eia_api_key:
            params["api_key"] = settings.eia_api_key
        try:
            response = await self.client.get(request_url, params=params)
        except httpx.TransportError:
            return build_mapping_probe_result(
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
                        "transport", "transport_error", "EIA request was unreachable"
                    ),
                ),
            )

        raw = response.content
        digest = sha256(raw).hexdigest()
        content_type = response.headers.get("content-type", "application/json")
        if not 200 <= response.status_code < 300:
            return build_mapping_probe_result(
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
                        "http", "http_status", f"EIA returned HTTP {response.status_code}"
                    ),
                ),
            )
        try:
            payload = response.json()
        except ValueError:
            payload = None
        response_payload = payload.get("response") if isinstance(payload, dict) else None
        if (
            not isinstance(payload, dict)
            or payload.get("error")
            or not isinstance(response_payload, dict)
            or not isinstance(response_payload.get("data"), list)
        ):
            return build_mapping_probe_result(
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
                        "EIA response did not contain a successful data payload",
                    ),
                ),
            )

        details: dict[str, Any] = {
            "total": response_payload.get("total"),
            "frequency": response_payload.get("frequency"),
            "date_format": response_payload.get("dateFormat"),
            "value_field": "value",
        }
        rows = response_payload["data"]
        row = rows[0] if len(rows) == 1 and isinstance(rows[0], dict) else {}
        details.update(
            {
                "first_period": row.get("period"),
                "row_series": row.get("series"),
                "units": row.get("units"),
            }
        )
        identity_issues: list[MappingProbeIssue] = []
        try:
            total = int(response_payload.get("total"))
        except (TypeError, ValueError):
            total = 0
        details["total"] = total
        checks = (
            (total > 0, "total_invalid", "EIA response total must be positive"),
            (
                response_payload.get("frequency") == "daily",
                "frequency_drift",
                "EIA response frequency must be daily",
            ),
            (
                response_payload.get("dateFormat") == "YYYY-MM-DD",
                "date_format_drift",
                "EIA response dateFormat must be YYYY-MM-DD",
            ),
            (len(rows) == 1, "row_count_invalid", "EIA probe must return one row"),
            (
                row.get("period") == expected_first_period,
                "first_period_drift",
                "EIA first period does not match the pinned boundary",
            ),
            (
                row.get("series") == provider_series_id,
                "series_identity_drift",
                "EIA row series does not match provider_series_id",
            ),
            (row.get("units") == "$/BBL", "units_drift", "EIA units must be $/BBL"),
            (
                "value" in row and parse_decimal(row.get("value")) is not None,
                "value_invalid",
                "EIA value field must be present and parseable",
            ),
        )
        for passed, code, message in checks:
            if not passed:
                identity_issues.append(MappingProbeIssue("identity", code, message))
        if not authorized:
            identity_issues.append(
                MappingProbeIssue(
                    "authorization",
                    "authorization_missing",
                    "EIA API authorization is unavailable",
                )
            )
        return build_mapping_probe_result(
            provider_code=provider.code,
            source_series_id=source.id,
            provider_series_id=provider_series_id,
            request_url=request_url,
            http_status=response.status_code,
            content_type=content_type,
            official_description=str(response_payload.get("description") or "").strip(),
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
        if not settings.eia_api_key:
            raise RuntimeError("EIA_API_KEY is required")
        results: list[ProviderFetchResult] = []
        for source, dataset in mappings:
            locator = source.source_locator
            route = locator.get("route")
            if not route:
                raise ProviderDataError(f"EIA mapping {source.id} has no route")
            url = self._route_url(str(route), bool(locator.get("append_data_path", False)))
            cutoff = (
                date.min
                if mode in {"backfill", "vintage_backfill"}
                else date.today() - timedelta(days=365 * 5)
            )
            data_fields = locator.get("data_fields") or [str(locator.get("value_field") or "value")]
            if not isinstance(data_fields, list) or not data_fields:
                raise ProviderDataError(
                    f"EIA mapping {source.id} data_fields must be a non-empty list"
                )
            value_field = str(locator.get("value_field") or data_fields[0])
            base_params: dict[str, Any] = {
                "api_key": settings.eia_api_key,
                "length": self.page_size,
                "sort[0][column]": str(locator.get("sort_column") or "period"),
                "sort[0][direction]": str(locator.get("sort_direction") or "asc"),
            }
            for index, field in enumerate(data_fields):
                base_params[f"data[{index}]"] = str(field)
            if locator.get("frequency"):
                base_params["frequency"] = str(locator["frequency"])
            facets = locator.get("facets") or {}
            if not isinstance(facets, dict):
                raise ProviderDataError(f"EIA mapping {source.id} facets must be an object")
            for facet, values in facets.items():
                values_list = values if isinstance(values, list) else [values]
                for index, value in enumerate(values_list):
                    base_params[f"facets[{facet}][{index}]"] = str(value)
            if mode not in {"backfill", "vintage_backfill"}:
                base_params["start"] = cutoff.isoformat()

            offset = 0
            pages: list[dict[str, Any]] = []
            rows_by_period: dict[date, dict[str, Any]] = {}
            request_log: list[dict[str, Any]] = []
            last_request_url = url
            content_type = "application/json"
            expected_total: int | None = None
            seen_page_signatures: set[tuple[str, ...]] = set()

            for _page in range(self.max_pages):
                params = {**base_params, "offset": offset}
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ProviderDataError("EIA response was not an object")
                if payload.get("error"):
                    raise ProviderDataError(f"EIA API error: {payload.get('error')}")
                response_payload = payload.get("response", {})
                if not isinstance(response_payload, dict):
                    raise ProviderDataError("EIA response did not contain a response object")
                rows = response_payload.get("data", []) or []
                if not isinstance(rows, list):
                    raise ProviderDataError("EIA response.data was not a list")
                pages.append(payload)
                request_log.append(params)
                last_request_url = str(response.request.url)
                content_type = response.headers.get("content-type", "application/json")

                signature = tuple(str(row.get("period") or row.get("date") or "") for row in rows)
                if signature and signature in seen_page_signatures:
                    raise ProviderDataError(
                        "EIA pagination repeated a page; refusing incomplete history"
                    )
                seen_page_signatures.add(signature)

                for raw_row in rows:
                    if not isinstance(raw_row, dict):
                        raise ProviderDataError("EIA response.data contained a non-object row")
                    period_text = str(raw_row.get("period") or raw_row.get("date") or "")
                    period = self._parse_period(period_text)
                    if period is None:
                        raise ProviderDataError(
                            f"EIA returned an invalid period {period_text!r} for source {source.id}"
                        )
                    if period < cutoff:
                        raise ProviderDataError(
                            f"EIA returned {period} before requested cutoff {cutoff}"
                        )
                    if value_field not in raw_row:
                        raise ProviderDataError(
                            f"EIA row for source {source.id} omitted value field {value_field!r}"
                        )
                    previous = rows_by_period.get(period)
                    if previous is not None:
                        raise ProviderDataError(
                            f"EIA returned more than one row for source {source.id} at {period}; "
                            "pin all facets before enabling the mapping"
                        )
                    rows_by_period[period] = raw_row

                total_raw = response_payload.get("total")
                try:
                    total = int(total_raw) if total_raw is not None else None
                except (TypeError, ValueError):
                    total = None
                if expected_total is None:
                    expected_total = total
                elif total is not None and expected_total != total:
                    raise ProviderDataError("EIA total changed during pagination")
                received = len(rows)
                offset += received
                if (
                    received == 0
                    or (total is not None and offset >= total)
                    or received < self.page_size
                ):
                    break
            else:
                raise ProviderDataError(
                    f"EIA pagination exceeded {self.max_pages} pages for {route}"
                )

            if expected_total is not None and offset < expected_total:
                raise ProviderDataError(
                    f"EIA pagination incomplete for {route}: received {offset} "
                    f"of {expected_total} rows"
                )
            fetched_at = datetime.now(UTC)
            observations: list[NormalizedObservation] = []
            for period, row in sorted(rows_by_period.items()):
                value = parse_decimal(row.get(value_field))
                observations.append(
                    NormalizedObservation(
                        source_series_id=source.id,
                        period_start=period,
                        period_end=period_end(period, source.source_frequency or "daily"),
                        value=value,
                        status="missing" if value is None else "normal",
                        vintage_at=fetched_at,
                        source_updated_at=fetched_at,
                        quality_flags=["missing_value"] if value is None else [],
                    )
                )
            observations = deduplicate_observations(observations)
            raw_bundle = json.dumps(
                {"provider": self.code, "requests": request_log, "responses": pages},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=dataset,
                    request_url=last_request_url,
                    request_parameters={"requests": request_log},
                    content_type=content_type,
                    raw_bytes=raw_bundle,
                    observations=observations,
                )
            )
        return results

    @staticmethod
    def _route_url(route: str, append_data_path: bool) -> str:
        clean = route.strip("/")
        if append_data_path and not clean.endswith("/data"):
            clean = f"{clean}/data"
        return f"https://api.eia.gov/{clean}/"

    @staticmethod
    def _parse_period(value: str) -> date | None:
        text = value.strip().upper()
        if not text:
            return None
        if "-Q" in text:
            year, quarter = text.split("-Q", 1)
            if year.isdigit() and quarter.isdigit() and 1 <= int(quarter) <= 4:
                return date(int(year), (int(quarter) - 1) * 3 + 1, 1)
        if len(text) == 4 and text.isdigit():
            return date(int(text), 1, 1)
        if len(text) == 7 and text[4] == "-":
            try:
                return date.fromisoformat(f"{text}-01")
            except ValueError:
                return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
