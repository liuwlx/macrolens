from __future__ import annotations

import json
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
                    f"Census mapping {source.id} is unresolved; approve official dictionary dimensions first"
                )
            value_field = str(locator.get("value_field") or "cell_value")
            time_field = str(locator.get("time_field") or "time")
            dimensions = locator.get("dimensions") or {}
            if not isinstance(dimensions, dict) or not dimensions:
                raise ProviderDataError(f"Census mapping {source.id} has no pinned dimensions")

            required_variables = locator.get("required_variables") or []
            if not isinstance(required_variables, list):
                raise ProviderDataError(f"Census mapping {source.id} required_variables must be a list")
            get_fields = list(
                dict.fromkeys(
                    [
                        value_field,
                        time_field,
                        "time_slot_date",
                        *required_variables,
                        *[key for key in dimensions if key != "for"],
                    ]
                )
            )
            path = str(locator.get("path") or f"timeseries/eits/{dataset.code}").strip("/")
            url = f"https://api.census.gov/data/{path}"
            start_value = str(locator.get("start") or (locator.get("start_year") or 1990))
            if mode not in {"backfill", "vintage_backfill"}:
                start_value = str(current_year - 5)
            end_value = str(locator.get("end") or current_year)
            time_value = f"from+{start_value}+to+{end_value}"
            params: dict[str, Any] = {
                "get": ",".join(get_fields),
                "time": time_value,
                "key": settings.census_api_key,
            }
            for key, value in dimensions.items():
                if value is None or value == "":
                    # Census uses bare predicate variables for some datasets.
                    params[str(key)] = ""
                else:
                    params[str(key)] = str(value)

            response = await self.client.get(url, params=params)
            response.raise_for_status()
            payload = response.json()
            fetched_at = datetime.now(UTC)
            observations: list[NormalizedObservation] = []
            if not isinstance(payload, list) or not payload:
                raise ProviderDataError(f"Census mapping {source.id} returned an invalid matrix payload")
            headers = [str(item) for item in payload[0]]
            required_headers = {value_field}
            if time_field not in headers and "time" not in headers and "time_slot_date" not in headers:
                required_headers.add(time_field)
            required_headers.update(
                str(key)
                for key, expected in dimensions.items()
                if expected not in {None, ""}
            )
            missing_headers = required_headers - set(headers)
            if missing_headers:
                raise ProviderDataError(
                    f"Census mapping {source.id} response is missing fields {sorted(missing_headers)}"
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
                    raise ProviderDataError(
                        f"Census mapping {source.id} returned a row outside pinned dimensions: {row}"
                    )
                time_text = str(
                    row.get(time_field)
                    or row.get("time_slot_date")
                    or row.get("time")
                    or ""
                )
                period = self._parse_period(time_text)
                if period is None:
                    raise ProviderDataError(
                        f"Census mapping {source.id} returned an invalid time value {time_text!r}"
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
            observations = deduplicate_observations(observations)
            raw_bundle = json.dumps(
                {"provider": self.code, "request": params, "response": payload},
                ensure_ascii=False,
                separators=(",", ":"),
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
    def _dimensions_match(row: dict[str, Any], dimensions: dict[str, Any]) -> bool:
        for key, expected in dimensions.items():
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
