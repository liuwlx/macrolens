from __future__ import annotations

import calendar
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

import httpx

from macrolens_api.models import Dataset, Provider, SourceSeries


class ProviderDataError(RuntimeError):
    """Raised when an upstream response is syntactically valid but not safe to publish."""


@dataclass(frozen=True, slots=True)
class NormalizedObservation:
    source_series_id: int
    period_start: date
    period_end: date
    value: Decimal | None
    value_text: str | None = None
    status: str = "normal"
    published_at: datetime | None = None
    vintage_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_updated_at: datetime | None = None
    quality_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProviderFetchResult:
    provider: Provider
    dataset: Dataset | None
    request_url: str
    request_parameters: dict[str, Any]
    content_type: str
    raw_bytes: bytes
    observations: list[NormalizedObservation]
    source_last_modified: datetime | None = None


class ProviderAdapter(ABC):
    code: str

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    @abstractmethod
    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        raise NotImplementedError


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {".", "NA", "N/A", "(NA)", "null", "None", "--"}:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def period_end(period_start: date, frequency: str) -> date:
    normalized = frequency.lower().replace("_", "-")
    if normalized == "daily":
        return period_start
    if normalized == "weekly":
        return period_start + timedelta(days=6)
    if normalized == "monthly":
        last = calendar.monthrange(period_start.year, period_start.month)[1]
        return period_start.replace(day=last)
    if normalized == "quarterly":
        month = period_start.month + 2
        last = calendar.monthrange(period_start.year, month)[1]
        return date(period_start.year, month, last)
    if normalized in {"semiannual", "semi-annual"}:
        month = 6 if period_start.month == 1 else 12
        last = calendar.monthrange(period_start.year, month)[1]
        return date(period_start.year, month, last)
    if normalized == "annual":
        return date(period_start.year, 12, 31)
    return period_start


def parse_period_code(year: int, period_code: str, frequency: str) -> date | None:
    """Parse BLS-style period codes without silently treating quarterly data as monthly."""

    code = period_code.strip().upper()
    normalized = frequency.lower().replace("_", "-")
    if code.startswith("M") and code[1:].isdigit():
        month = int(code[1:])
        if 1 <= month <= 12:
            return date(year, month, 1)
        if month == 13 and normalized == "annual":
            return date(year, 1, 1)
        return None
    if code.startswith("Q"):
        digits = re.sub(r"\D", "", code)
        quarter = int(digits) if digits else 0
        if 1 <= quarter <= 4:
            return date(year, (quarter - 1) * 3 + 1, 1)
        return None
    if code.startswith("S") or code.startswith("H"):
        digits = re.sub(r"\D", "", code)
        half = int(digits) if digits else 0
        if 1 <= half <= 2:
            return date(year, 1 if half == 1 else 7, 1)
        return None
    if code.startswith("A") and normalized == "annual":
        return date(year, 1, 1)
    return None


def normalize_label(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def deduplicate_observations(
    observations: Iterable[NormalizedObservation],
) -> list[NormalizedObservation]:
    """Remove exact duplicate rows and reject contradictory rows in one source snapshot."""

    seen: dict[tuple[int, date, datetime], NormalizedObservation] = {}
    for item in observations:
        if item.period_end < item.period_start:
            raise ProviderDataError(
                f"Invalid period for source_series_id={item.source_series_id}: "
                f"{item.period_start}..{item.period_end}"
            )
        key = (item.source_series_id, item.period_start, item.vintage_at)
        previous = seen.get(key)
        if previous is None:
            seen[key] = item
            continue
        comparable_previous = (
            previous.period_end,
            previous.value,
            previous.value_text,
            previous.status,
            previous.published_at,
        )
        comparable_current = (
            item.period_end,
            item.value,
            item.value_text,
            item.status,
            item.published_at,
        )
        if comparable_previous != comparable_current:
            raise ProviderDataError(
                "Conflicting duplicate upstream rows for "
                f"source_series_id={item.source_series_id}, period={item.period_start}, "
                f"vintage={item.vintage_at.isoformat()}"
            )
    return sorted(
        seen.values(),
        key=lambda item: (item.source_series_id, item.period_start, item.vintage_at),
    )


def apply_mapping_transform(
    observations: list[NormalizedObservation], source: SourceSeries
) -> list[NormalizedObservation]:
    transformed = observations
    transform = source.source_locator.get("transform")
    if transform == "period_difference":
        periods = int(source.source_locator.get("periods", 1))
        ordered = sorted(observations, key=lambda item: item.period_start)
        result: list[NormalizedObservation] = []
        for index, item in enumerate(ordered):
            value: Decimal | None = None
            flags = list(item.quality_flags)
            if index >= periods:
                previous = ordered[index - periods]
                expected_previous = _shift_period(
                    item.period_start, source.source_frequency or "monthly", -periods
                )
                if previous.period_start != expected_previous:
                    flags.append("derived_missing_predecessor")
                elif item.value is not None and previous.value is not None:
                    value = item.value - previous.value
            result.append(
                NormalizedObservation(
                    source_series_id=item.source_series_id,
                    period_start=item.period_start,
                    period_end=item.period_end,
                    value=value,
                    status=item.status,
                    published_at=item.published_at,
                    vintage_at=item.vintage_at,
                    source_updated_at=item.source_updated_at,
                    quality_flags=flags + ["derived_period_difference"],
                )
            )
        transformed = result
    elif transform not in {None, "", "identity"}:
        raise ProviderDataError(f"Unsupported source mapping transform: {transform!r}")

    scale_raw = source.source_locator.get("scale_factor")
    if scale_raw is None:
        return transformed
    try:
        scale = Decimal(str(scale_raw))
    except Exception as exc:
        raise ProviderDataError(f"Invalid source scale_factor={scale_raw!r}") from exc
    if scale == 0:
        raise ProviderDataError("source scale_factor cannot be zero")
    scaled: list[NormalizedObservation] = []
    for item in transformed:
        scaled.append(
            NormalizedObservation(
                source_series_id=item.source_series_id,
                period_start=item.period_start,
                period_end=item.period_end,
                value=item.value * scale if item.value is not None else None,
                value_text=item.value_text,
                status=item.status,
                published_at=item.published_at,
                vintage_at=item.vintage_at,
                source_updated_at=item.source_updated_at,
                quality_flags=[*item.quality_flags, f"scaled_by:{scale}"],
            )
        )
    return scaled


def _shift_period(value: date, frequency: str, periods: int) -> date:
    normalized = frequency.lower().replace("_", "-")
    if normalized == "monthly":
        month_index = value.year * 12 + value.month - 1 + periods
        return date(month_index // 12, month_index % 12 + 1, 1)
    if normalized == "quarterly":
        month_index = value.year * 12 + value.month - 1 + periods * 3
        return date(month_index // 12, month_index % 12 + 1, 1)
    if normalized in {"semiannual", "semi-annual"}:
        month_index = value.year * 12 + value.month - 1 + periods * 6
        return date(month_index // 12, month_index % 12 + 1, 1)
    if normalized == "annual":
        return date(value.year + periods, 1, 1)
    if normalized == "weekly":
        return value + timedelta(days=periods * 7)
    return value + timedelta(days=periods)
