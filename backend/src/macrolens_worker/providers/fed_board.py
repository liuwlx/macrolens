from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from io import BytesIO
from zipfile import ZipFile

from lxml import etree  # type: ignore[import-untyped]

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


class FederalReserveBoardAdapter(ProviderAdapter):
    """Configuration-driven adapter for Federal Reserve Board release files.

    The first supported release is G.17's ``ip_sa.txt`` file. Release-specific parsing
    stays behind this adapter while file URLs, identities, and history requirements remain
    in the source registry.
    """

    code = "FED_BOARD_FILES"
    g17_url = "https://www.federalreserve.gov/releases/g17/current/ipdisk/ip_sa.txt"

    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        del mode
        grouped: dict[str, list[tuple[SourceSeries, Dataset]]] = defaultdict(list)
        for source, dataset in mappings:
            url = str(source.source_locator.get("file_url") or self.g17_url)
            grouped[url].append((source, dataset))

        results: list[ProviderFetchResult] = []
        for url, file_mappings in grouped.items():
            response = await self.client.get(url)
            response.raise_for_status()
            fetched_at = datetime.now(UTC)
            observations: list[NormalizedObservation] = []
            for source, _dataset in file_mappings:
                format_name = str(source.source_locator.get("format") or "g17_ip_sa")
                if format_name not in {"g17_ip_sa", "sdmx_xml_zip"}:
                    raise ProviderDataError(
                        f"Federal Reserve Board mapping {source.id} has unsupported format "
                        f"{format_name!r}"
                    )
                if format_name == "g17_ip_sa":
                    observations.extend(self._parse_g17(response.content, source, fetched_at))
                else:
                    observations.extend(
                        self._parse_sdmx_xml_zip(response.content, source, fetched_at)
                    )
            observations = deduplicate_observations(observations)
            last_modified = self._last_modified(response.headers.get("last-modified"))
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=file_mappings[0][1],
                    request_url=url,
                    request_parameters={"file_url": url},
                    content_type=response.headers.get("content-type", "text/plain"),
                    raw_bytes=response.content,
                    observations=observations,
                    source_last_modified=last_modified,
                )
            )
        return results

    @classmethod
    def _parse_g17(
        cls,
        raw: bytes,
        source: SourceSeries,
        vintage_at: datetime | None,
    ) -> list[NormalizedObservation]:
        series_code = str(
            source.source_locator.get("series_code") or source.provider_series_id or ""
        )
        expected_description = str(source.source_locator.get("line_description") or "").strip()
        if not series_code:
            raise ProviderDataError(f"G.17 mapping {source.id} has no series_code")
        if not expected_description:
            raise ProviderDataError(f"G.17 mapping {source.id} has no line_description")

        text = raw.decode("utf-8-sig")
        descriptions: dict[str, str] = {}
        rows: list[tuple[str, int, list[str]]] = []
        allow_partial_latest_year = bool(
            source.source_locator.get("allow_partial_latest_year", False)
        )
        header_pattern = re.compile(r'^\s*"([^":]+):\s*(.*?)"\s*$')
        data_pattern = re.compile(r'^\s*"([^"]+)"\s+(\d{4})(.*)$')
        for _line_number, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            header_match = header_pattern.match(line)
            if header_match:
                descriptions[header_match.group(1).strip()] = header_match.group(2).strip()
                continue
            data_match = data_pattern.match(line)
            if not data_match:
                continue
            values = data_match.group(3).split()
            if data_match.group(1).strip() != series_code:
                continue
            rows.append((data_match.group(1).strip(), int(data_match.group(2)), values))

        actual_description = descriptions.get(series_code)
        if actual_description != expected_description:
            raise ProviderDataError(
                f"G.17 mapping {source.id} line_description mismatch: "
                f"expected {expected_description!r}, received {actual_description!r}"
            )

        matching_rows = [row for row in rows if row[0] == series_code]
        if not matching_rows:
            raise ProviderDataError(f"G.17 mapping {source.id} returned no {series_code} rows")

        latest_year = max(row[1] for row in matching_rows)
        for _code, year, values in matching_rows:
            if len(values) == 12:
                continue
            if not (
                allow_partial_latest_year
                and year == latest_year
                and 1 <= len(values) <= 12
            ):
                raise ProviderDataError(
                    f"G.17 mapping {source.id} row for {year} has "
                    f"{len(values)} monthly values; expected 12 monthly values"
                )

        observed_vintage = vintage_at or datetime.now(UTC)
        observations: list[NormalizedObservation] = []
        for _code, year, values in matching_rows:
            for month, raw_value in enumerate(values, start=1):
                period = date(year, month, 1)
                value = parse_decimal(raw_value)
                observations.append(
                    NormalizedObservation(
                        source_series_id=source.id,
                        period_start=period,
                        period_end=period_end(period, source.source_frequency or "monthly"),
                        value=value,
                        status="missing" if value is None else "normal",
                        vintage_at=observed_vintage,
                        source_updated_at=observed_vintage,
                        quality_flags=["missing_value"] if value is None else [],
                    )
                )

        expected_first = source.source_locator.get("expected_first_period")
        if expected_first:
            try:
                expected_first_date = date.fromisoformat(str(expected_first))
            except ValueError as exc:
                raise ProviderDataError(
                    f"G.17 mapping {source.id} has invalid expected_first_period {expected_first!r}"
                ) from exc
            actual_first = min(item.period_start for item in observations)
            if actual_first != expected_first_date:
                raise ProviderDataError(
                    f"G.17 mapping {source.id} begins at {actual_first}; "
                    f"expected {expected_first_date}"
                )
        return observations

    @classmethod
    def _parse_sdmx_xml_zip(
        cls,
        raw: bytes,
        source: SourceSeries,
        vintage_at: datetime | None,
    ) -> list[NormalizedObservation]:
        series_name = str(
            source.source_locator.get("series_name") or source.provider_series_id or ""
        )
        if not series_name:
            raise ProviderDataError(f"Board XML mapping {source.id} has no series_name")
        member_name = str(source.source_locator.get("zip_member") or "")
        try:
            with ZipFile(BytesIO(raw)) as archive:
                candidates = [name for name in archive.namelist() if name.endswith("_data.xml")]
                selected = member_name or (candidates[0] if candidates else "")
                if not selected:
                    raise ProviderDataError("Board XML ZIP has no *_data.xml member")
                xml = archive.read(selected)
        except (OSError, ValueError, KeyError) as exc:
            raise ProviderDataError("Board response was not a readable XML ZIP") from exc
        try:
            root = etree.fromstring(xml)
        except etree.XMLSyntaxError as exc:
            raise ProviderDataError("Board XML data member was invalid") from exc

        matches = [
            item
            for item in root.xpath('//*[local-name()="Series"]')
            if item.attrib.get("SERIES_NAME") == series_name
        ]
        if len(matches) != 1:
            raise ProviderDataError(
                f"Board XML mapping {source.id} resolved {len(matches)} rows for {series_name}"
            )
        series = matches[0]
        for key, expected in (source.source_locator.get("series_attributes") or {}).items():
            actual = series.attrib.get(str(key))
            if actual != str(expected):
                raise ProviderDataError(
                    f"Board XML mapping {source.id} attribute {key} expected {expected!r}, "
                    f"received {actual!r}"
                )

        observed_vintage = vintage_at or datetime.now(UTC)
        frequency = source.source_frequency or "daily"
        scale = source.source_locator.get("value_scale_to_platform_unit")
        observations: list[NormalizedObservation] = []
        for obs in series.xpath('./*[local-name()="Obs"]'):
            raw_period = str(obs.attrib.get("TIME_PERIOD") or "")
            try:
                period = date.fromisoformat(raw_period[:10])
            except ValueError as exc:
                raise ProviderDataError(
                    f"Board XML mapping {source.id} has invalid TIME_PERIOD {raw_period!r}"
                ) from exc
            if frequency == "quarterly":
                period = date(period.year, ((period.month - 1) // 3) * 3 + 1, 1)
            elif frequency == "monthly":
                period = date(period.year, period.month, 1)
            value = parse_decimal(obs.attrib.get("OBS_VALUE"))
            if value is not None and scale is not None:
                from decimal import Decimal

                try:
                    value *= Decimal(str(scale))
                except Exception as exc:
                    raise ProviderDataError(
                        f"Board XML mapping {source.id} has invalid value scale {scale!r}"
                    ) from exc
            observations.append(
                NormalizedObservation(
                    source_series_id=source.id,
                    period_start=period,
                    period_end=period_end(period, frequency),
                    value=value,
                    status="missing" if value is None else "normal",
                    vintage_at=observed_vintage,
                    source_updated_at=observed_vintage,
                    quality_flags=["missing_value"] if value is None else [],
                )
            )
        if not observations:
            raise ProviderDataError(f"Board XML mapping {source.id} returned no observations")
        expected_first = source.source_locator.get("expected_first_period")
        if expected_first:
            try:
                expected_first_date = date.fromisoformat(str(expected_first))
            except ValueError as exc:
                raise ProviderDataError(
                    f"Board XML mapping {source.id} has invalid expected_first_period"
                ) from exc
            actual_first = min(item.period_start for item in observations)
            if actual_first != expected_first_date:
                raise ProviderDataError(
                    f"Board XML mapping {source.id} begins at {actual_first}; "
                    f"expected {expected_first_date}"
                )
        return observations

    @staticmethod
    def _last_modified(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
