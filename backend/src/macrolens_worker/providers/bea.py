from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from typing import Any

from macrolens_api.config import get_settings
from macrolens_api.models import Dataset, Provider, SourceSeries

from .base import (
    NormalizedObservation,
    ProviderAdapter,
    ProviderDataError,
    ProviderFetchResult,
    deduplicate_observations,
    normalize_label,
    parse_decimal,
    period_end,
)


class BEAAdapter(ProviderAdapter):
    code = "BEA_API"
    endpoint = "https://apps.bea.gov/api/data"

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
            response = await self.client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()
            errors = payload.get("BEAAPI", {}).get("Error")
            if errors:
                raise ProviderDataError(f"BEA request failed: {errors}")
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
                for row in data_rows:
                    if not isinstance(row, dict):
                        raise ProviderDataError("BEA Data contained a non-object row")
                    if not self._row_matches(row, identity):
                        continue
                    period_text = str(row.get("TimePeriod", ""))
                    period = self._parse_period(period_text)
                    if period is None:
                        raise ProviderDataError(
                            f"BEA mapping {source.id} returned invalid TimePeriod {period_text!r}"
                        )
                    value = parse_decimal(row.get("DataValue"))
                    flags: list[str] = []
                    if value is None:
                        flags.append("missing_value")
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
                    "response": payload,
                },
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=dataset,
                    request_url=str(response.request.url),
                    request_parameters=params,
                    content_type=response.headers.get("content-type", "application/json"),
                    raw_bytes=raw_bundle,
                    observations=observations,
                )
            )
        return results

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
                    raise ProviderDataError(
                        f"BEA row identity {key} has conflicting descriptions: "
                        f"{previous!r} vs {description!r}"
                    )
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
                candidates = sorted(description for _, _, description in unique)[:10]
                raise ProviderDataError(
                    f"BEA mapping {source.id} must resolve to exactly one row; "
                    f"found {len(unique)} candidates: {candidates}"
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
