from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any

import httpx

from macrolens_api.config import get_settings
from macrolens_api.models import Dataset, Provider, SourceSeries

from .base import (
    MappingProbeResult,
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
    def _sanitized_payload(payload: dict[str, object]) -> dict[str, object]:
        """Return persistable request metadata without credentials."""

        return {key: value for key, value in payload.items() if key != "registrationkey"}

    @staticmethod
    def _persistable_response(body: dict[str, Any]) -> dict[str, Any]:
        """Drop volatile BLS timing telemetry while preserving replayable source data."""

        return {key: value for key, value in body.items() if key != "responseTime"}

    @staticmethod
    def _series_payloads(
        body: dict[str, Any], requested_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        if body.get("status") != "REQUEST_SUCCEEDED":
            raise ProviderDataError(
                "BLS business status was not REQUEST_SUCCEEDED: "
                f"{body.get('status')!r}; message={body.get('message')!r}"
            )
        result_object = body.get("Results", {})
        series_payloads = (
            result_object.get("series", []) if isinstance(result_object, dict) else []
        )
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
        missing_ids = sorted(set(requested_ids) - set(returned))
        unexpected_ids = sorted(set(returned) - set(requested_ids))
        if missing_ids or unexpected_ids:
            raise ProviderDataError(
                "BLS response series coverage mismatch: "
                f"missing={missing_ids}, unexpected={unexpected_ids}"
            )
        return returned

    @staticmethod
    def _validate_identity(
        source: SourceSeries,
        payload: dict[str, Any],
        *,
        require_pinned_title: bool = True,
    ) -> str:
        external_id = str(payload.get("seriesID") or "")
        if external_id != str(source.provider_series_id):
            expected = source.provider_series_id
            raise ProviderDataError(
                f"BLS identity mismatch: expected {expected!r}, got {external_id!r}"
            )
        catalog = payload.get("catalog")
        if not isinstance(catalog, dict):
            if not require_pinned_title:
                return ""
            raise ProviderDataError(f"BLS catalog metadata missing for {external_id}")
        actual_title = str(catalog.get("series_title") or "").strip()
        expected_title = str(source.source_locator.get("expected_catalog_title") or "").strip()
        if not expected_title and require_pinned_title:
            raise ProviderDataError(
                f"BLS mapping {source.id} has no pinned expected_catalog_title"
            )
        if expected_title and actual_title != expected_title:
            raise ProviderDataError(
                f"BLS catalog title mismatch for {external_id}: {actual_title!r}"
            )
        expected_catalog = source.source_locator.get("expected_catalog", {})
        if expected_catalog and not isinstance(expected_catalog, dict):
            raise ProviderDataError(
                f"BLS mapping {source.id} expected_catalog must be an object"
            )
        for field, expected in expected_catalog.items():
            actual = catalog.get(field)
            if str(actual or "").strip() != str(expected).strip():
                raise ProviderDataError(
                    f"BLS catalog {field} mismatch for {external_id}: {actual!r}"
                )
        return actual_title

    async def probe(
        self,
        provider: Provider,
        source: SourceSeries,
        dataset: Dataset,
    ) -> MappingProbeResult:
        """Probe one mapping without writing observations or exposing credentials."""

        del dataset  # The exact dataset identity is already bound by the SourceSeries row.
        if not source.provider_series_id:
            raise ProviderDataError(f"BLS mapping {source.id} has no provider_series_id")
        settings = get_settings()
        current_year = date.today().year
        payload: dict[str, object] = {
            "seriesid": [str(source.provider_series_id)],
            "startyear": str(current_year - 1),
            "endyear": str(current_year - 1),
            "catalog": True,
            "calculations": False,
            "annualaverage": False,
            "aspects": False,
        }
        if settings.bls_api_key:
            payload["registrationkey"] = settings.bls_api_key
        probed_at = datetime.now(UTC)
        authorized = bool(settings.bls_api_key)
        try:
            response = await self.client.post(self.endpoint, json=payload)
        except httpx.TransportError:
            return MappingProbeResult(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=str(source.provider_series_id),
                request_url=self.endpoint,
                http_reachable=False,
                http_status=None,
                content_type="",
                business_success=False,
                identity_match=False,
                official_description="",
                response_sha256="",
                probed_at=probed_at,
                authorization_available=authorized,
                production_ready=False,
                classification="BLOCKED",
            )
        raw = response.content
        digest = sha256(raw).hexdigest()
        content_type = response.headers.get("content-type", "application/json")
        if not 200 <= response.status_code < 300:
            return MappingProbeResult(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=str(source.provider_series_id),
                request_url=self.endpoint,
                http_reachable=True,
                http_status=response.status_code,
                content_type=content_type,
                business_success=False,
                identity_match=False,
                official_description="",
                response_sha256=digest,
                probed_at=probed_at,
                authorization_available=authorized,
                production_ready=False,
                classification="BLOCKED",
            )
        try:
            body = response.json()
        except ValueError:
            body = None
        if not isinstance(body, dict):
            return MappingProbeResult(
                provider_code=provider.code,
                source_series_id=source.id,
                provider_series_id=str(source.provider_series_id),
                request_url=self.endpoint,
                http_reachable=True,
                http_status=response.status_code,
                content_type=content_type,
                business_success=False,
                identity_match=False,
                official_description="",
                response_sha256=digest,
                probed_at=probed_at,
                authorization_available=authorized,
                production_ready=False,
                classification="BLOCKED",
            )
        business_success = body.get("status") == "REQUEST_SUCCEEDED"
        official_description = ""
        identity_match = False
        if business_success:
            try:
                returned = self._series_payloads(body, [str(source.provider_series_id)])
                official_description = self._validate_identity(
                    source, returned[str(source.provider_series_id)]
                )
                identity_match = True
            except ProviderDataError:
                identity_match = False
        production_ready = business_success and identity_match and authorized
        return MappingProbeResult(
            provider_code=provider.code,
            source_series_id=source.id,
            provider_series_id=str(source.provider_series_id),
            request_url=self.endpoint,
            http_reachable=True,
            http_status=response.status_code,
            content_type=content_type,
            business_success=business_success,
            identity_match=identity_match,
            official_description=official_description,
            response_sha256=digest,
            probed_at=probed_at,
            authorization_available=authorized,
            production_ready=production_ready,
            classification=(
                "PASS"
                if production_ready
                else "AUTH_REQUIRED"
                if business_success and identity_match
                else "BLOCKED"
            ),
        )

    @classmethod
    def replay(
        cls,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        raw_bytes: bytes,
        *,
        vintage_at: datetime,
    ) -> ProviderFetchResult:
        """Replay a sanitized raw BLS bundle with no network access."""

        try:
            bundle = json.loads(raw_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderDataError("BLS replay bundle was not valid UTF-8 JSON") from exc
        if not isinstance(bundle, dict) or bundle.get("provider") != cls.code:
            raise ProviderDataError("BLS replay bundle has the wrong provider identity")
        requests = bundle.get("requests")
        responses = bundle.get("responses")
        if not isinstance(requests, list) or not isinstance(responses, list):
            raise ProviderDataError("BLS replay bundle omitted requests or responses")
        if len(requests) != len(responses) or not requests:
            raise ProviderDataError("BLS replay bundle request/response count mismatch")
        if any(isinstance(item, dict) and "registrationkey" in item for item in requests):
            raise ProviderDataError("BLS replay bundle contains credential material")

        source_by_external = {
            str(source.provider_series_id): source for source, _dataset in mappings
        }
        datasets = {dataset.id: dataset for _source, dataset in mappings}
        if len(source_by_external) != len(mappings) or len(datasets) != 1:
            raise ProviderDataError("BLS replay requires unique mappings from one dataset")
        source_rows: dict[int, dict[date, NormalizedObservation]] = defaultdict(dict)
        for request_item, response_item in zip(requests, responses, strict=True):
            if not isinstance(request_item, dict) or not isinstance(response_item, dict):
                raise ProviderDataError("BLS replay request/response entries must be objects")
            requested_ids = [str(item) for item in request_item.get("seriesid", [])]
            if not requested_ids or any(item not in source_by_external for item in requested_ids):
                raise ProviderDataError("BLS replay requested an unmapped series")
            try:
                window_start = int(request_item["startyear"])
                window_end = int(request_item["endyear"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderDataError("BLS replay request has invalid year bounds") from exc
            returned = cls._series_payloads(response_item, requested_ids)
            for external_id, series_payload in returned.items():
                source = source_by_external[external_id]
                cls._validate_identity(source, series_payload)
                cls._collect_observations(
                    source_rows,
                    source,
                    series_payload,
                    window_start=window_start,
                    window_end=window_end,
                    vintage_at=vintage_at,
                )
        observations: list[NormalizedObservation] = []
        for source, _dataset in mappings:
            complete = sorted(source_rows[source.id].values(), key=lambda item: item.period_start)
            observations.extend(
                deduplicate_observations(apply_mapping_transform(complete, source))
            )
        return ProviderFetchResult(
            provider=provider,
            dataset=next(iter(datasets.values())),
            request_url=cls.endpoint,
            request_parameters={"requests": requests},
            content_type="application/json",
            raw_bytes=raw_bytes,
            observations=observations,
            captured_at=vintage_at,
        )

    @staticmethod
    def _collect_observations(
        source_rows: dict[int, dict[date, NormalizedObservation]],
        source: SourceSeries,
        series_payload: dict[str, Any],
        *,
        window_start: int,
        window_end: int,
        vintage_at: datetime,
    ) -> None:
        external_id = str(source.provider_series_id)
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
            if period_code == "M13":
                continue
            period = parse_period_code(
                row_year, period_code, source.source_frequency or "monthly"
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
            source_start_year = int(source.source_locator.get("start_year", window_start))
            source_end_year = int(source.source_locator.get("end_year", window_end))
            if not source_start_year <= period.year <= source_end_year:
                continue
            value = parse_decimal(row.get("value"))
            footnotes = row.get("footnotes", [])
            if not isinstance(footnotes, list):
                raise ProviderDataError(f"BLS footnotes for {external_id} were not a list")
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
                period_end=period_end(period, source.source_frequency or "monthly"),
                value=value,
                status=(
                    "missing"
                    if value is None
                    else "latest_provider_observation"
                    if latest
                    else "normal"
                ),
                vintage_at=vintage_at,
                source_updated_at=vintage_at,
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
            captured_at = datetime.now(UTC)
            source_by_external = {str(source.provider_series_id): source for source in sources}
            if len(source_by_external) != len(sources):
                raise ProviderDataError(
                    "BLS dataset contains duplicate provider_series_id mappings"
                )
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
                    if not isinstance(body, dict):
                        raise ProviderDataError("BLS response was not an object")
                    returned = self._series_payloads(body, batch_ids)

                    request_log.append(self._sanitized_payload(payload))
                    raw_responses.append(self._persistable_response(body))
                    content_types.add(response.headers.get("content-type", "application/json"))

                    for external_id, series_payload in returned.items():
                        source = source_by_external[external_id]
                        self._validate_identity(
                            source,
                            series_payload,
                            require_pinned_title=bool(
                                source.source_locator.get("expected_catalog_title")
                            ),
                        )
                        self._collect_observations(
                            source_rows,
                            source,
                            series_payload,
                            window_start=window_start,
                            window_end=window_end,
                            vintage_at=captured_at,
                        )

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
                    captured_at=captured_at,
                )
            )
        return results
