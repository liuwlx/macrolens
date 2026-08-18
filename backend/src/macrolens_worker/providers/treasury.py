from __future__ import annotations

import json
from datetime import UTC, date, datetime
from hashlib import sha256

import httpx
from lxml import etree  # type: ignore[import-untyped]

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


class TreasuryAdapter(ProviderAdapter):
    code = "US_TREASURY_XML"

    FIELD_MAP = {
        "2Y_PAR_NOMINAL": "BC_2YEAR",
        "10Y_PAR_NOMINAL": "BC_10YEAR",
        "10Y_PAR_REAL": "TC_10YEAR",
    }

    async def probe(
        self,
        provider: Provider,
        source: SourceSeries,
        dataset: Dataset,
    ) -> MappingProbeResult:
        probed_at = datetime.now(UTC)
        provider_series_id = str(source.provider_series_id) if source.provider_series_id else None
        field = self.FIELD_MAP.get(provider_series_id or "")
        request_url = (
            "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
        )
        if not field:
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
                        "unsupported_series",
                        "Treasury provider_series_id is not pinned to a supported curve field",
                    ),
                ),
            )
        kind = (
            "daily_treasury_real_yield_curve"
            if provider_series_id == "10Y_PAR_REAL"
            else "daily_treasury_yield_curve"
        )
        params = {"data": kind, "field_tdr_date_value": str(date.today().year)}
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
                        "transport", "transport_error", "Treasury request was unreachable"
                    ),
                ),
            )
        raw = response.content
        digest = sha256(raw).hexdigest()
        content_type = response.headers.get("content-type", "application/xml")
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
                    MappingProbeIssue("http", "http_status", "Treasury returned a non-2xx status"),
                ),
            )
        try:
            observations = self._parse(raw, [(source, dataset)])
        except ProviderDataError:
            observations = []
        identity_match = bool(observations)
        issues = (
            ()
            if identity_match
            else (
                MappingProbeIssue(
                    "identity",
                    "field_not_observed",
                    "Treasury response did not expose the pinned curve field",
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
            official_description=provider_series_id or "",
            response_sha256=digest,
            probed_at=probed_at,
            evidence=MappingProbeEvidence(
                True,
                True,
                True,
                identity_match,
                True,
                {"field": field, "observation_count": len(observations)},
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
        current_year = date.today().year
        nominal = [
            (source, dataset)
            for source, dataset in mappings
            if source.provider_series_id != "10Y_PAR_REAL"
        ]
        real = [
            (source, dataset)
            for source, dataset in mappings
            if source.provider_series_id == "10Y_PAR_REAL"
        ]
        results: list[ProviderFetchResult] = []
        for kind, kind_mappings, default_start in (
            ("daily_treasury_yield_curve", nominal, 1990),
            ("daily_treasury_real_yield_curve", real, 2003),
        ):
            if not kind_mappings:
                continue
            start_year = min(
                int(getattr(source, "source_locator", {}).get("start_year", default_start))
                for source, _ in kind_mappings
            )
            years = (
                range(start_year, current_year + 1)
                if mode in {"backfill", "vintage_backfill"}
                else range(current_year - 5, current_year + 1)
            )
            for year in years:
                url = "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml"
                params = {"data": kind, "field_tdr_date_value": str(year)}
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                observations = deduplicate_observations(
                    self._parse(response.content, kind_mappings)
                )
                outside_year = [item for item in observations if item.period_start.year != year]
                if outside_year:
                    raise ProviderDataError(
                        f"Treasury {kind} returned {len(outside_year)} rows outside "
                        f"requested year {year}"
                    )
                observed_source_ids = {item.source_series_id for item in observations}
                missing_sources = [
                    source.id
                    for source, _dataset in kind_mappings
                    if year
                    >= int(
                        (getattr(source, "source_locator", {}) or {}).get(
                            "start_year", default_start
                        )
                    )
                    and source.id not in observed_source_ids
                ]
                if missing_sources:
                    raise ProviderDataError(
                        f"Treasury {kind} returned no observations for source mappings "
                        f"{missing_sources} in year {year}"
                    )
                raw_bundle = json.dumps(
                    {"provider": self.code, "request": params, "xml": response.text},
                    ensure_ascii=False,
                    separators=(",", ":"),
                ).encode("utf-8")
                results.append(
                    ProviderFetchResult(
                        provider=provider,
                        dataset=kind_mappings[0][1],
                        request_url=str(response.request.url),
                        request_parameters=params,
                        content_type=response.headers.get("content-type", "application/xml"),
                        raw_bytes=raw_bundle,
                        observations=observations,
                    )
                )
        return results

    def _parse(
        self, raw: bytes, mappings: list[tuple[SourceSeries, Dataset]]
    ) -> list[NormalizedObservation]:
        try:
            root = etree.fromstring(raw)
        except etree.XMLSyntaxError as exc:
            raise ProviderDataError("Treasury response was not valid XML") from exc
        fetched_at = datetime.now(UTC)
        observations: list[NormalizedObservation] = []
        entries = root.xpath("//*[local-name()='entry']")
        for entry in entries:
            properties = entry.xpath(".//*[local-name()='properties']")
            if not properties:
                continue
            values: dict[str, str | None] = {}
            for child in properties[0]:
                is_null = any(
                    etree.QName(key).localname == "null" and str(value).lower() == "true"
                    for key, value in child.attrib.items()
                )
                values[etree.QName(child).localname] = None if is_null else child.text
            date_text = values.get("NEW_DATE") or values.get("Date") or values.get("date")
            if not date_text:
                continue
            try:
                period = date.fromisoformat(str(date_text)[:10])
            except ValueError:
                try:
                    period = datetime.strptime(str(date_text)[:10], "%m/%d/%Y").date()
                except ValueError as exc:
                    raise ProviderDataError(
                        f"Treasury XML contained an invalid date {date_text!r}"
                    ) from exc
            for source, _dataset in mappings:
                field = self.FIELD_MAP.get(source.provider_series_id or "")
                if not field:
                    raise ProviderDataError(
                        f"Treasury mapping {source.id} has unsupported series "
                        f"{source.provider_series_id}"
                    )
                value = parse_decimal(values.get(field))
                if value is None:
                    # Treasury publishes null fields on dates before a maturity existed. They are
                    # absence of an observation, not a revised observation with a null value.
                    continue
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
        return observations
