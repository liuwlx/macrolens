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
    apply_mapping_transform,
    deduplicate_observations,
    parse_decimal,
    parse_period_code,
    period_end,
)


class BLSAdapter(ProviderAdapter):
    """Strict BLS v2 adapter.

    BLS limits a registered v2 request to 50 series and a 20-year range. Full history is
    therefore assembled from non-overlapping legal windows and only published when every
    requested series is present and every row can be parsed without contradiction.
    """

    code = "BLS_API_V2"
    endpoint = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
    batch_size = 50
    year_span = 20

    @staticmethod
    def _year_windows(start_year: int, end_year: int, span: int) -> list[tuple[int, int]]:
        windows: list[tuple[int, int]] = []
        current = start_year
        while current <= end_year:
            window_end = min(current + span - 1, end_year)
            windows.append((current, window_end))
            current = window_end + 1
        return windows

    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        settings = get_settings()
        if not settings.bls_api_key:
            raise RuntimeError("BLS_API_KEY is required; BLS registration is required for API v2")
        current_year = date.today().year
        backfill = mode in {"backfill", "vintage_backfill"}

        by_dataset: dict[int, tuple[Dataset, list[SourceSeries]]] = {}
        for source, dataset in mappings:
            if not source.provider_series_id:
                raise ProviderDataError(f"BLS mapping {source.id} has no provider_series_id")
            bucket = by_dataset.setdefault(dataset.id, (dataset, []))
            bucket[1].append(source)

        results: list[ProviderFetchResult] = []
        for dataset, sources in by_dataset.values():
            source_by_external = {str(source.provider_series_id): source for source in sources}
            if len(source_by_external) != len(sources):
                raise ProviderDataError("BLS dataset contains duplicate provider_series_id mappings")
            start_year = (
                min(int(source.source_locator.get("start_year", 1913)) for source in sources)
                if backfill
                else current_year - 5
            )
            source_rows: dict[int, dict[date, NormalizedObservation]] = defaultdict(dict)
            request_log: list[dict[str, Any]] = []
            raw_responses: list[dict[str, Any]] = []
            content_types: set[str] = set()

            for window_start, window_end in self._year_windows(
                start_year, current_year, self.year_span
            ):
                eligible = [
                    source
                    for source in sources
                    if int(source.source_locator.get("start_year", start_year)) <= window_end
                    and int(source.source_locator.get("end_year", current_year)) >= window_start
                ]
                for batch_start in range(0, len(eligible), self.batch_size):
                    batch_sources = eligible[batch_start : batch_start + self.batch_size]
                    if not batch_sources:
                        continue
                    batch_ids = [str(source.provider_series_id) for source in batch_sources]
                    payload: dict[str, object] = {
                        "seriesid": batch_ids,
                        "startyear": str(window_start),
                        "endyear": str(window_end),
                        "catalog": True,
                        "calculations": False,
                        "annualaverage": False,
                        "aspects": False,
                        "registrationkey": settings.bls_api_key,
                    }
                    response = await self.client.post(self.endpoint, json=payload)
                    response.raise_for_status()
                    body = response.json()
                    if body.get("status") != "REQUEST_SUCCEEDED":
                        raise ProviderDataError(f"BLS request failed: {body.get('message')}")
                    result_object = body.get("Results", {})
                    series_payloads = result_object.get("series", []) if isinstance(result_object, dict) else []
                    if not isinstance(series_payloads, list):
                        raise ProviderDataError("BLS Results.series was not a list")
                    returned: dict[str, dict[str, Any]] = {}
                    for item in series_payloads:
                        if not isinstance(item, dict):
                            raise ProviderDataError("BLS Results.series contained a non-object row")
                        external_id = str(item.get("seriesID") or "")
                        if not external_id:
                            raise ProviderDataError("BLS series payload omitted seriesID")
                        if external_id in returned:
                            raise ProviderDataError(
                                f"BLS returned duplicate series payloads for {external_id}"
                            )
                        returned[external_id] = item
                    missing_ids = sorted(set(batch_ids) - set(returned))
                    unexpected_ids = sorted(set(returned) - set(batch_ids))
                    if missing_ids or unexpected_ids:
                        raise ProviderDataError(
                            "BLS response series coverage mismatch: "
                            f"missing={missing_ids}, unexpected={unexpected_ids}"
                        )

                    fetched_at = datetime.now(UTC)
                    request_log.append(payload)
                    raw_responses.append(body)
                    content_types.add(response.headers.get("content-type", "application/json"))

                    for external_id, series_payload in returned.items():
                        source = source_by_external[external_id]
                        expected_title = source.source_locator.get("expected_catalog_title")
                        catalog = series_payload.get("catalog")
                        if expected_title:
                            if not isinstance(catalog, dict):
                                raise ProviderDataError(
                                    f"BLS catalog metadata missing for {external_id}"
                                )
                            actual_title = str(catalog.get("series_title") or "").strip()
                            if actual_title != str(expected_title).strip():
                                raise ProviderDataError(
                                    f"BLS catalog title mismatch for {external_id}: {actual_title!r}"
                                )
                        data_rows = series_payload.get("data", [])
                        if not isinstance(data_rows, list):
                            raise ProviderDataError(f"BLS data for {external_id} was not a list")
                        for row in data_rows:
                            if not isinstance(row, dict):
                                raise ProviderDataError(
                                    f"BLS data for {external_id} contained a non-object row"
                                )
                            try:
                                row_year = int(row["year"])
                            except (KeyError, TypeError, ValueError) as exc:
                                raise ProviderDataError(
                                    f"BLS row for {external_id} has invalid year: {row}"
                                ) from exc
                            period_code = str(row.get("period", "")).upper()
                            # M13 is BLS's annual-average pseudo-period and is not a monthly
                            # observation. It is intentionally omitted because annualaverage=false.
                            if period_code == "M13":
                                continue
                            period = parse_period_code(
                                row_year,
                                period_code,
                                source.source_frequency or "monthly",
                            )
                            if period is None:
                                raise ProviderDataError(
                                    f"BLS row for {external_id} has unsupported period {period_code!r}"
                                )
                            if not window_start <= period.year <= window_end:
                                raise ProviderDataError(
                                    f"BLS row for {external_id} escaped requested year window "
                                    f"{window_start}-{window_end}: {period}"
                                )
                            source_start_year = int(
                                source.source_locator.get("start_year", start_year)
                            )
                            source_end_year = int(
                                source.source_locator.get("end_year", current_year)
                            )
                            if period.year < source_start_year or period.year > source_end_year:
                                continue
                            value = parse_decimal(row.get("value"))
                            footnotes = row.get("footnotes", [])
                            if not isinstance(footnotes, list):
                                raise ProviderDataError(
                                    f"BLS footnotes for {external_id} were not a list"
                                )
                            flags = [
                                str(footnote.get("text"))
                                for footnote in footnotes
                                if isinstance(footnote, dict) and footnote.get("text")
                            ]
                            if value is None:
                                flags.append("missing_value")
                            latest = str(row.get("latest", "")).lower() == "true"
                            observation = NormalizedObservation(
                                source_series_id=source.id,
                                period_start=period,
                                period_end=period_end(
                                    period, source.source_frequency or "monthly"
                                ),
                                value=value,
                                status=(
                                    "missing"
                                    if value is None
                                    else "latest_provider_observation"
                                    if latest
                                    else "normal"
                                ),
                                vintage_at=fetched_at,
                                source_updated_at=fetched_at,
                                quality_flags=flags,
                            )
                            previous = source_rows[source.id].get(period)
                            if previous is not None and (
                                previous.value,
                                previous.value_text,
                            ) != (observation.value, observation.value_text):
                                raise ProviderDataError(
                                    f"BLS returned conflicting values for {external_id} at {period}"
                                )
                            source_rows[source.id][period] = observation

            observations: list[NormalizedObservation] = []
            for source in sources:
                complete_history = sorted(
                    source_rows[source.id].values(), key=lambda item: item.period_start
                )
                transformed = apply_mapping_transform(complete_history, source)
                observations.extend(deduplicate_observations(transformed))

            raw_bundle = json.dumps(
                {"provider": self.code, "requests": request_log, "responses": raw_responses},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=dataset,
                    request_url=self.endpoint,
                    request_parameters={"requests": request_log},
                    content_type=(
                        "application/json"
                        if len(content_types) != 1
                        else next(iter(content_types))
                    ),
                    raw_bytes=raw_bundle,
                    observations=observations,
                )
            )
        return results
