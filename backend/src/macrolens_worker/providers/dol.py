from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime
from typing import Any

import httpx

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


class DOLOpenDataAdapter(ProviderAdapter):
    """Configurable strict adapter for DOL unemployment-insurance claims data.

    DOL's modern portal can expose different endpoint contracts. The endpoint, row fields and
    pagination contract are therefore explicit registry data. The adapter never guesses missing
    pages or silently drops malformed rows.
    """

    code = "DOL_OPEN_DATA_API"
    max_pages = 10000

    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        settings = get_settings()
        results: list[ProviderFetchResult] = []
        for source, dataset in mappings:
            locator = source.source_locator
            url = str(locator.get("url") or settings.dol_claims_url or "")
            if not url:
                raise RuntimeError(
                    "DOL_CLAIMS_URL is required and must point to the verified DOL claims endpoint"
                )
            date_field = str(locator.get("date_field") or "week_ending")
            value_field = str(locator.get("value_field") or "initial_claims_seasonally_adjusted")
            pagination = locator.get("pagination") or {}
            if not isinstance(pagination, dict):
                raise ProviderDataError(f"DOL mapping {source.id} pagination must be an object")
            page_size = int(pagination.get("page_size") or 5000)
            if page_size <= 0:
                raise ProviderDataError(f"DOL mapping {source.id} has invalid page_size")
            offset_param = str(pagination.get("offset_param") or "offset")
            limit_param = str(pagination.get("limit_param") or "limit")
            total_field = str(pagination.get("total_field") or "total")
            pagination_enabled = bool(pagination.get("enabled", False))
            base_params = dict(locator.get("params") or {})

            all_rows: list[dict[str, Any]] = []
            raw_pages: list[dict[str, Any]] = []
            request_log: list[dict[str, Any]] = []
            page_signatures: set[tuple[tuple[str, str], ...]] = set()
            offset = 0
            expected_total: int | None = None
            last_response: httpx.Response | None = None
            for _ in range(self.max_pages):
                params = dict(base_params)
                if pagination_enabled:
                    params[offset_param] = offset
                    params[limit_param] = page_size
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                last_response = response
                content_type = response.headers.get("content-type", "application/json")
                payload: Any
                if "json" in content_type.lower():
                    payload = response.json()
                else:
                    payload = response.content.decode("utf-8-sig", errors="replace")
                rows = self._rows(response.content, content_type)
                signature = tuple(
                    sorted(
                        (str(row.get(date_field) or ""), str(row.get(value_field) or ""))
                        for row in rows
                    )
                )
                if signature and signature in page_signatures:
                    raise ProviderDataError("DOL pagination repeated a page")
                page_signatures.add(signature)
                total = self._find_total(payload, total_field)
                if expected_total is None:
                    expected_total = total
                elif total is not None and expected_total != total:
                    raise ProviderDataError("DOL total changed during pagination")
                all_rows.extend(rows)
                raw_pages.append({"payload": payload})
                request_log.append(params)
                if not pagination_enabled:
                    if total is not None and len(rows) < total:
                        raise ProviderDataError(
                            f"DOL endpoint declares {total} rows but pagination is disabled "
                            "and only "
                            f"{len(rows)} rows were returned"
                        )
                    break
                received = len(rows)
                offset += received
                if received == 0 or received < page_size or (total is not None and offset >= total):
                    break
            else:
                raise ProviderDataError(f"DOL pagination exceeded {self.max_pages} pages")

            if expected_total is not None and len(all_rows) < expected_total:
                raise ProviderDataError(
                    f"DOL pagination incomplete: received {len(all_rows)} of {expected_total} rows"
                )
            fetched_at = datetime.now(UTC)
            observations: list[NormalizedObservation] = []
            seen_periods: set[date] = set()
            for row in all_rows:
                raw_date = row.get(date_field) or row.get("date") or row.get("weekEnding")
                if not raw_date:
                    raise ProviderDataError(
                        f"DOL mapping {source.id} returned a row without {date_field!r}"
                    )
                period = self._parse_date(str(raw_date))
                if period is None:
                    raise ProviderDataError(
                        f"DOL mapping {source.id} returned invalid date {raw_date!r}"
                    )
                if value_field not in row:
                    raise ProviderDataError(
                        f"DOL mapping {source.id} returned a row without {value_field!r}"
                    )
                if period in seen_periods:
                    raise ProviderDataError(
                        f"DOL mapping {source.id} returned duplicate period {period}; "
                        "refusing ambiguous history"
                    )
                seen_periods.add(period)
                value = parse_decimal(row.get(value_field))
                flags = ["missing_value"] if value is None else []
                observations.append(
                    NormalizedObservation(
                        source_series_id=source.id,
                        period_start=period,
                        period_end=period_end(period, source.source_frequency or "weekly"),
                        value=value,
                        status="missing" if value is None else "normal",
                        vintage_at=fetched_at,
                        source_updated_at=fetched_at,
                        quality_flags=flags,
                    )
                )
            observations = deduplicate_observations(observations)
            if last_response is None:
                raise ProviderDataError("DOL adapter made no request")
            raw_bundle = json.dumps(
                {"provider": self.code, "requests": request_log, "pages": raw_pages},
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
            results.append(
                ProviderFetchResult(
                    provider=provider,
                    dataset=dataset,
                    request_url=str(last_response.request.url),
                    request_parameters={"requests": request_log},
                    content_type="application/json",
                    raw_bytes=raw_bundle,
                    observations=observations,
                )
            )
        return results

    @staticmethod
    def _parse_date(value: str) -> date | None:
        text = value.strip()
        for parser in (
            lambda: date.fromisoformat(text[:10]),
            lambda: datetime.strptime(text[:10], "%m/%d/%Y").date(),
            lambda: datetime.strptime(text[:10], "%m-%d-%Y").date(),
        ):
            try:
                return parser()
            except ValueError:
                continue
        return None

    @staticmethod
    def _find_total(payload: Any, total_field: str) -> int | None:
        if not isinstance(payload, dict):
            return None
        candidates = [payload.get(total_field)]
        for key in ("meta", "metadata", "pagination"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                candidates.append(nested.get(total_field))
        for value in candidates:
            try:
                return int(value) if value is not None else None
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _rows(raw: bytes, content_type: str) -> list[dict[str, Any]]:
        if "json" in content_type.lower():
            payload = json.loads(raw)
            if isinstance(payload, list):
                if not all(isinstance(row, dict) for row in payload):
                    raise ProviderDataError("DOL JSON array contained a non-object row")
                return payload
            if isinstance(payload, dict):
                for key in ("data", "results", "items", "records"):
                    value = payload.get(key)
                    if isinstance(value, list):
                        if not all(isinstance(row, dict) for row in value):
                            raise ProviderDataError(
                                f"DOL JSON {key} array contained a non-object row"
                            )
                        return value
                    if isinstance(value, dict):
                        for nested_key in ("data", "records", "items"):
                            nested = value.get(nested_key)
                            if isinstance(nested, list):
                                if not all(isinstance(row, dict) for row in nested):
                                    raise ProviderDataError(
                                        f"DOL JSON {key}.{nested_key} contained a non-object row"
                                    )
                                return nested
            return []
        text = raw.decode("utf-8-sig", errors="replace")
        return [dict(row) for row in csv.DictReader(io.StringIO(text))]
