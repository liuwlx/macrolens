from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from typing import Any

import httpx

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
    deduplicate_observations,
    parse_decimal,
    period_end,
)


class NYFedAdapter(ProviderAdapter):
    """New York Fed markets adapter with bounded date windows and strict row coverage."""

    code = "NYFED_MARKETS_API"

    async def probe(
        self,
        provider: Provider,
        source: SourceSeries,
        dataset: Dataset,
    ) -> MappingProbeResult:
        del dataset
        probed_at = datetime.now(UTC)
        provider_series_id = str(source.provider_series_id) if source.provider_series_id else None
        route = str(source.source_locator.get("route") or "").strip().lstrip("/")
        request_url = (
            f"https://markets.newyorkfed.org/api/{route}"
            if route
            else "https://markets.newyorkfed.org/api"
        )
        if not provider_series_id or not route:
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
                evidence=MappingProbeEvidence(True, False, False, False, True),
                issues=(
                    MappingProbeIssue(
                        "configuration",
                        "route_or_identity_missing",
                        "NY Fed route and provider_series_id must be pinned before probing",
                    ),
                ),
            )
        today = date.today()
        params: dict[str, Any] = {
            "startDate": (today - timedelta(days=7)).isoformat(),
            "endDate": today.isoformat(),
            "format": "json",
        }
        if route.startswith("rates/"):
            params["type"] = str(source.source_locator.get("type") or "rate")
        params.update(dict(source.source_locator.get("params") or {}))
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
                evidence=MappingProbeEvidence(False, False, False, False, True),
                issues=(
                    MappingProbeIssue(
                        "transport", "transport_error", "NY Fed request was unreachable"
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
                evidence=MappingProbeEvidence(True, False, False, False, True),
                issues=(
                    MappingProbeIssue("http", "http_status", "NY Fed returned a non-2xx status"),
                ),
            )
        try:
            payload = response.json()
            rows = self._find_rows(payload)
        except (ValueError, ProviderDataError):
            rows = []
        if not rows:
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
                evidence=MappingProbeEvidence(True, True, False, False, True),
                issues=(
                    MappingProbeIssue(
                        "business", "empty_response", "NY Fed returned no probe rows"
                    ),
                ),
            )
        values: list[tuple[str, Decimal]] = []
        field = str(source.source_locator.get("field") or "") or None
        for row in rows:
            period = self._parse_date(
                row.get("effectiveDate") or row.get("operationDate") or row.get("date")
            )
            value = parse_decimal(self._value(row, provider_series_id, field))
            if period is not None and value is not None:
                values.append((period.isoformat(), value))
        identity_match = bool(values)
        issues = (
            ()
            if identity_match
            else (
                MappingProbeIssue(
                    "identity",
                    "value_field_mismatch",
                    "NY Fed rows did not expose the pinned numeric value",
                ),
            )
        )
        return _build_mapping_probe_result(
            provider_code=provider.code,
            source_series_id=source.id,
            provider_series_id=provider_series_id,
            request_url=request_url,
            http_status=response.status_code,
            content_type=content_type,
            official_description=provider_series_id,
            response_sha256=digest,
            probed_at=probed_at,
            evidence=MappingProbeEvidence(
                True,
                True,
                True,
                identity_match,
                True,
                {
                    "first_period": values[0][0] if values else None,
                    "value_field": field or "provider_default",
                },
            ),
            issues=issues,
        )

    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        today = date.today()
        backfill = mode in {"backfill", "vintage_backfill"}
        results: list[ProviderFetchResult] = []
        for source, dataset in mappings:
            locator = source.source_locator
            route = locator.get("route")
            if not route:
                raise ProviderDataError(f"NY Fed mapping {source.id} has no route")
            url = f"https://markets.newyorkfed.org/api/{str(route).lstrip('/')}"
            configured_start = self._parse_date(locator.get("start_date"))
            start = configured_start or (
                date(2000, 1, 1) if backfill else today - timedelta(days=365 * 5)
            )
            if not backfill:
                start = max(start, today - timedelta(days=365 * 5))
            if start > today:
                raise ProviderDataError(f"NY Fed mapping {source.id} starts after today")

            windows = self._annual_windows(start, today) if backfill else [(start, today)]
            raw_responses: list[dict[str, Any]] = []
            request_log: list[dict[str, Any]] = []
            values_by_period: dict[date, list[Decimal]] = defaultdict(list)
            last_url = url
            content_type = "application/json"
            field = locator.get("field")
            aggregation = str(
                locator.get("aggregation")
                or ("sum" if source.provider_series_id == "RRP_TOTAL_ACCEPTED" else "unique")
            )
            allow_empty_windows = bool(locator.get("allow_empty_windows", False))

            for window_start, window_end in windows:
                params: dict[str, Any] = {
                    "startDate": window_start.isoformat(),
                    "endDate": window_end.isoformat(),
                    "format": "json",
                }
                if str(route).startswith("rates/"):
                    params["type"] = str(locator.get("type") or "rate")
                params.update(dict(locator.get("params") or {}))
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
                rows = self._find_rows(payload)
                request_log.append(params)
                raw_responses.append(payload)
                last_url = str(response.request.url)
                content_type = response.headers.get("content-type", "application/json")
                if not rows:
                    if allow_empty_windows:
                        continue
                    raise ProviderDataError(
                        f"NY Fed mapping {source.id} returned no rows for "
                        f"{window_start}..{window_end}"
                    )

                parsed_in_window = 0
                for row in rows:
                    period_value = (
                        row.get("effectiveDate") or row.get("operationDate") or row.get("date")
                    )
                    if not period_value:
                        raise ProviderDataError(
                            f"NY Fed mapping {source.id} returned a row without a date"
                        )
                    period = self._parse_date(period_value)
                    if period is None:
                        raise ProviderDataError(
                            f"NY Fed mapping {source.id} returned invalid date {period_value!r}"
                        )
                    if not window_start <= period <= window_end:
                        raise ProviderDataError(
                            f"NY Fed mapping {source.id} returned {period} outside requested "
                            f"window {window_start}..{window_end}"
                        )
                    raw_value = self._value(
                        row,
                        source.provider_series_id,
                        str(field) if field else None,
                    )
                    value = parse_decimal(raw_value)
                    if value is None:
                        raise ProviderDataError(
                            f"NY Fed mapping {source.id} has no numeric value at {period}"
                        )
                    values_by_period[period].append(value)
                    parsed_in_window += 1
                if parsed_in_window == 0:
                    raise ProviderDataError(
                        f"NY Fed mapping {source.id} yielded no parseable observations for "
                        f"{window_start}..{window_end}"
                    )

            fetched_at = datetime.now(UTC)
            observations: list[NormalizedObservation] = []
            for period, values in sorted(values_by_period.items()):
                value = self._aggregate(values, aggregation, source.id, period)
                observations.append(
                    NormalizedObservation(
                        source_series_id=source.id,
                        period_start=period,
                        period_end=period_end(period, source.source_frequency or "daily"),
                        value=value,
                        status="normal",
                        vintage_at=fetched_at,
                        source_updated_at=fetched_at,
                    )
                )
            observations = deduplicate_observations(observations)
            raw_bundle = json.dumps(
                {
                    "provider": self.code,
                    "requests": request_log,
                    "responses": raw_responses,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=dataset,
                    request_url=last_url,
                    request_parameters={"requests": request_log},
                    content_type=content_type,
                    raw_bytes=raw_bundle,
                    observations=observations,
                )
            )
        return results

    @staticmethod
    def _annual_windows(start: date, end: date) -> list[tuple[date, date]]:
        windows: list[tuple[date, date]] = []
        current = start
        while current <= end:
            window_end = min(date(current.year, 12, 31), end)
            windows.append((current, window_end))
            current = window_end + timedelta(days=1)
        return windows

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if value is None:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    @staticmethod
    def _aggregate(values: list[Decimal], method: str, source_id: int, period: date) -> Decimal:
        if not values:
            raise ProviderDataError(f"NY Fed source {source_id} has no numeric value at {period}")
        if method == "sum":
            return sum(values, Decimal("0"))
        if method == "max":
            return max(values)
        if method == "last":
            return values[-1]
        if method != "unique":
            raise ProviderDataError(
                f"NY Fed source {source_id} has unsupported aggregation {method!r}"
            )
        if len(set(values)) != 1:
            raise ProviderDataError(
                f"NY Fed source {source_id} returned conflicting values at {period}: {values}"
            )
        return values[0]

    @staticmethod
    def _find_rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            if not all(isinstance(item, dict) for item in payload):
                raise ProviderDataError("NY Fed response list contained a non-object row")
            return payload
        if isinstance(payload, dict):
            for key in ("refRates", "repo", "operations", "data", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    if not all(isinstance(item, dict) for item in value):
                        raise ProviderDataError(f"NY Fed response {key} contained a non-object row")
                    return value
                if isinstance(value, dict):
                    for nested_key in ("rates", "operations", "data", "results"):
                        nested_value = value.get(nested_key)
                        if isinstance(nested_value, list):
                            if not all(isinstance(item, dict) for item in nested_value):
                                raise ProviderDataError(
                                    f"NY Fed response {key}.{nested_key} contained a non-object row"
                                )
                            return nested_value
            for value in payload.values():
                nested = NYFedAdapter._find_rows(value)
                if nested:
                    return nested
        return []

    @staticmethod
    def _value(row: dict[str, Any], series_id: str | None, field: str | None) -> Any:
        if field and field in row:
            return row[field]
        candidates = {
            "EFFR": ["percentRate", "rate", "effectiveRate"],
            "SOFR": ["percentRate", "rate"],
            "RRP_TOTAL_ACCEPTED": ["totalAmtAccepted", "totalAmountAccepted"],
        }.get(series_id or "", ["value", "rate"])
        for candidate in candidates:
            if candidate in row:
                return row[candidate]
        return None
