from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
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
    period_end,
)


class FREDAdapter(ProviderAdapter):
    code = "FRED_API"
    observations_url = "https://api.stlouisfed.org/fred/series/observations"
    vintage_dates_url = "https://api.stlouisfed.org/fred/series/vintagedates"
    series_url = "https://api.stlouisfed.org/fred/series"
    page_size = 100000
    vintage_chunk_size = 100
    max_pages = 10000

    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        settings = get_settings()
        if not settings.fred_api_key:
            raise RuntimeError("FRED_API_KEY is required")
        results: list[ProviderFetchResult] = []
        default_start = (
            date(1900, 1, 1)
            if mode in {"backfill", "vintage_backfill"}
            else date.today() - timedelta(days=365 * 5)
        )
        for source, dataset in mappings:
            if not source.provider_series_id:
                raise ProviderDataError(f"FRED mapping {source.id} has no provider_series_id")
            request_log: list[dict[str, Any]] = []
            responses: list[dict[str, Any]] = []
            metadata = await self._fetch_series_metadata(
                source, settings.fred_api_key, request_log, responses
            )
            start = default_start
            if mode in {"backfill", "vintage_backfill"}:
                metadata_start = self._parse_observation_date(metadata.get("observation_start"))
                verified_start = self._parse_observation_date(
                    source.source_locator.get("expected_first_period")
                    or source.source_locator.get("observation_start")
                )
                # A registry-pinned boundary is the contract. Never move the request forward merely
                # because upstream metadata changed; that would hide a truncated history. Metadata
                # identity validation below rejects disagreements before any observations publish.
                start = verified_start or metadata_start or default_start
            capture_vintages = mode == "vintage_backfill" or bool(
                source.source_locator.get("capture_vintages", False) and mode == "backfill"
            )
            if capture_vintages:
                vintage_dates = await self._fetch_vintage_dates(
                    source.provider_series_id,
                    settings.fred_api_key,
                    request_log,
                    responses,
                )
                observations = await self._fetch_vintage_observations(
                    source,
                    start,
                    vintage_dates,
                    settings.fred_api_key,
                    request_log,
                    responses,
                )
            else:
                observations = await self._fetch_current_observations(
                    source,
                    start,
                    settings.fred_api_key,
                    request_log,
                    responses,
                )
            if mode in {"backfill", "vintage_backfill"}:
                self._validate_backfill_start(source, observations, start)
            observations = apply_mapping_transform(observations, source)
            observations = deduplicate_observations(observations)
            raw_bundle = json.dumps(
                {"provider": self.code, "requests": request_log, "responses": responses},
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=dataset,
                    request_url=self.observations_url,
                    request_parameters={"requests": request_log},
                    content_type="application/json",
                    raw_bytes=raw_bundle,
                    observations=observations,
                )
            )
        return results

    @staticmethod
    def _validate_backfill_start(
        source: SourceSeries,
        observations: list[NormalizedObservation],
        expected_start: date,
    ) -> None:
        if bool(source.source_locator.get("allow_source_start_gap", False)):
            return
        if not observations:
            raise ProviderDataError(
                f"FRED backfill for {source.provider_series_id} returned no observations"
            )
        earliest = min(item.period_start for item in observations)
        if earliest != expected_start:
            raise ProviderDataError(
                f"FRED backfill for {source.provider_series_id} begins at {earliest}, "
                f"expected metadata start {expected_start}"
            )

    async def _fetch_series_metadata(
        self,
        source: SourceSeries,
        api_key: str,
        request_log: list[dict[str, Any]],
        responses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        params = {
            "series_id": source.provider_series_id,
            "api_key": api_key,
            "file_type": "json",
        }
        response = await self.client.get(self.series_url, params=params)
        response.raise_for_status()
        payload = response.json()
        request_log.append({"url": self.series_url, **params})
        responses.append(payload)
        series_rows = payload.get("seriess", [])
        if not isinstance(series_rows, list) or len(series_rows) != 1:
            raise ProviderDataError(
                f"FRED metadata for {source.provider_series_id} did not resolve to one series"
            )
        metadata = series_rows[0]
        if not isinstance(metadata, dict) or str(metadata.get("id")) != str(
            source.provider_series_id
        ):
            raise ProviderDataError(
                f"FRED metadata identity mismatch for {source.provider_series_id}: {metadata}"
            )
        expected_frequency = {
            "daily": "D",
            "weekly": "W",
            "monthly": "M",
            "quarterly": "Q",
            "semiannual": "SA",
            "semi-annual": "SA",
            "annual": "A",
        }.get((source.source_frequency or "").lower())
        actual_frequency = str(metadata.get("frequency_short") or "").upper()
        if (
            expected_frequency
            and actual_frequency
            and not actual_frequency.startswith(expected_frequency)
        ):
            raise ProviderDataError(
                f"FRED frequency mismatch for {source.provider_series_id}: "
                f"expected {expected_frequency}, received {actual_frequency}"
            )
        expected_first = self._parse_observation_date(
            source.source_locator.get("expected_first_period")
        )
        metadata_first = self._parse_observation_date(metadata.get("observation_start"))
        if (
            expected_first is not None
            and metadata_first is not None
            and metadata_first != expected_first
            and not bool(source.source_locator.get("allow_source_start_gap", False))
        ):
            raise ProviderDataError(
                f"FRED history boundary mismatch for {source.provider_series_id}: "
                f"registry expects {expected_first}, metadata reports {metadata_first}"
            )
        expected_title = source.source_locator.get("expected_title")
        if (
            expected_title
            and str(metadata.get("title") or "").strip() != str(expected_title).strip()
        ):
            raise ProviderDataError(
                f"FRED title mismatch for {source.provider_series_id}: {metadata.get('title')}"
            )
        return metadata

    @staticmethod
    def _parse_observation_date(value: Any) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    async def _fetch_current_observations(
        self,
        source: SourceSeries,
        start: date,
        api_key: str,
        request_log: list[dict[str, Any]],
        responses: list[dict[str, Any]],
    ) -> list[NormalizedObservation]:
        base_params: dict[str, Any] = {
            "series_id": source.provider_series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": start.isoformat(),
            "limit": self.page_size,
            "output_type": 1,
        }
        rows = await self._fetch_observation_pages(base_params, request_log, responses)
        fetched_at = datetime.now(UTC)
        return [
            self._normalize_row(source, row, fetched_at=fetched_at, use_source_vintage=False)
            for row in rows
        ]

    async def _fetch_vintage_dates(
        self,
        series_id: str,
        api_key: str,
        request_log: list[dict[str, Any]],
        responses: list[dict[str, Any]],
    ) -> list[str]:
        offset = 0
        values: list[str] = []
        expected_count: int | None = None
        for _ in range(self.max_pages):
            params: dict[str, str | int] = {
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "limit": min(self.page_size, 10000),
                "offset": offset,
                "sort_order": "asc",
            }
            response = await self.client.get(self.vintage_dates_url, params=params)
            response.raise_for_status()
            payload = response.json()
            request_log.append({"url": self.vintage_dates_url, **params})
            responses.append(payload)
            raw_page = payload.get("vintage_dates", [])
            if not isinstance(raw_page, list):
                raise ProviderDataError(f"FRED vintage_dates for {series_id} was not a list")
            page = [str(value) for value in raw_page]
            values.extend(page)
            try:
                count = int(payload.get("count", len(values)))
            except (TypeError, ValueError) as exc:
                raise ProviderDataError(f"FRED vintage count for {series_id} was invalid") from exc
            if expected_count is None:
                expected_count = count
            elif count != expected_count:
                raise ProviderDataError(
                    f"FRED vintage count changed during pagination for {series_id}"
                )
            offset += len(page)
            if not page or offset >= count:
                break
        else:
            raise ProviderDataError(f"FRED vintage date pagination exceeded {self.max_pages} pages")
        if expected_count is not None and len(values) < expected_count:
            raise ProviderDataError(
                f"FRED vintage pagination incomplete for {series_id}: "
                f"received {len(values)} of {expected_count}"
            )
        if len(values) != len(set(values)):
            raise ProviderDataError(f"FRED returned duplicate vintage dates for {series_id}")
        if not values:
            raise ProviderDataError(f"FRED returned no vintage dates for {series_id}")
        return values

    async def _fetch_vintage_observations(
        self,
        source: SourceSeries,
        start: date,
        vintage_dates: list[str],
        api_key: str,
        request_log: list[dict[str, Any]],
        responses: list[dict[str, Any]],
    ) -> list[NormalizedObservation]:
        observations: list[NormalizedObservation] = []
        for index in range(0, len(vintage_dates), self.vintage_chunk_size):
            chunk = vintage_dates[index : index + self.vintage_chunk_size]
            params: dict[str, Any] = {
                "series_id": source.provider_series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start.isoformat(),
                "limit": self.page_size,
                "output_type": 2,
                "vintage_dates": ",".join(chunk),
            }
            rows = await self._fetch_observation_pages(params, request_log, responses)
            fetched_at = datetime.now(UTC)
            observations.extend(
                self._normalize_row(source, row, fetched_at=fetched_at, use_source_vintage=True)
                for row in rows
            )
        return observations

    async def _fetch_observation_pages(
        self,
        base_params: dict[str, Any],
        request_log: list[dict[str, Any]],
        responses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        offset = 0
        rows: list[dict[str, Any]] = []
        expected_count: int | None = None
        seen_identities: dict[tuple[str, str, str], str] = {}
        for _ in range(self.max_pages):
            params = {**base_params, "offset": offset}
            response = await self.client.get(self.observations_url, params=params)
            response.raise_for_status()
            payload = response.json()
            page = payload.get("observations", [])
            if not isinstance(page, list):
                raise ProviderDataError("FRED observations was not a list")
            if not all(isinstance(row, dict) for row in page):
                raise ProviderDataError("FRED observations contained a non-object row")
            request_log.append({"url": self.observations_url, **params})
            responses.append(payload)
            for row in page:
                identity = (
                    str(row.get("date") or ""),
                    str(row.get("realtime_start") or ""),
                    str(row.get("realtime_end") or ""),
                )
                if not identity[0]:
                    raise ProviderDataError("FRED observation omitted date")
                value_text = str(row.get("value") or "")
                previous_value = seen_identities.get(identity)
                if previous_value is not None:
                    if previous_value != value_text:
                        raise ProviderDataError(
                            f"FRED returned conflicting duplicate observation {identity}"
                        )
                    raise ProviderDataError(
                        f"FRED pagination repeated observation {identity}; refusing "
                        "incomplete history"
                    )
                seen_identities[identity] = value_text
                rows.append(row)
            count: int | None
            try:
                count = int(payload.get("count"))
            except (TypeError, ValueError):
                count = len(rows) if len(page) < int(base_params["limit"]) else None
            if expected_count is None:
                expected_count = count
            elif count is not None and expected_count is not None and count != expected_count:
                raise ProviderDataError("FRED count changed during pagination")
            offset += len(page)
            if (
                not page
                or (count is not None and offset >= count)
                or len(page) < int(base_params["limit"])
            ):
                break
        else:
            raise ProviderDataError("FRED pagination exceeded configured maximum")
        if expected_count is not None and offset != expected_count:
            raise ProviderDataError(
                f"FRED pagination incomplete: received {offset} of {expected_count} observations"
            )
        return rows

    @staticmethod
    def _normalize_row(
        source: SourceSeries,
        row: dict[str, Any],
        *,
        fetched_at: datetime,
        use_source_vintage: bool,
    ) -> NormalizedObservation:
        try:
            period = date.fromisoformat(str(row["date"]))
        except (KeyError, ValueError) as exc:
            raise ProviderDataError(f"FRED row has invalid date: {row}") from exc
        realtime_start = FREDAdapter._parse_realtime(row.get("realtime_start"))
        realtime_end = FREDAdapter._parse_realtime(row.get("realtime_end"))
        if row.get("realtime_start") and realtime_start is None:
            raise ProviderDataError(f"FRED row has invalid realtime_start: {row}")
        if row.get("realtime_end") and realtime_end is None:
            raise ProviderDataError(f"FRED row has invalid realtime_end: {row}")
        value = parse_decimal(row.get("value"))
        flags: list[str] = []
        if value is None:
            flags.append("missing_value")
        if realtime_end and realtime_end.date().isoformat() != "9999-12-31":
            flags.append(f"realtime_end:{realtime_end.date().isoformat()}")
        return NormalizedObservation(
            source_series_id=source.id,
            period_start=period,
            period_end=period_end(period, source.source_frequency or "monthly"),
            value=value,
            status="missing" if value is None else "normal",
            vintage_at=(realtime_start or fetched_at) if use_source_vintage else fetched_at,
            source_updated_at=realtime_start,
            quality_flags=flags,
        )

    @staticmethod
    def _parse_realtime(value: Any) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value)).replace(tzinfo=UTC)
        except ValueError:
            return None
