from __future__ import annotations

from bisect import bisect_right
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from math import sqrt
from statistics import fmean, pstdev
from uuid import UUID


@dataclass(frozen=True, slots=True)
class Point:
    period_start: date
    period_end: date
    value: Decimal | None
    status: str
    published_at: object | None
    vintage_at: object
    value_text: str | None = None
    source_series_id: int | None = None
    run_id: UUID | None = None
    publication_batch_id: UUID | None = None
    raw_object_id: UUID | None = None


PERIODS_PER_YEAR = {
    "daily": 365,
    "weekly": 52,
    "monthly": 12,
    "quarterly": 4,
    "annual": 1,
}


def _valid_value(point: Point) -> Decimal | None:
    return point.value


def _shift_months(value: date, months: int) -> date:
    month_index = value.year * 12 + (value.month - 1) + months
    year, zero_based_month = divmod(month_index, 12)
    month = zero_based_month + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def _calendar_lag_index(
    points: list[Point],
    dates: list[date],
    exact_index: dict[date, int],
    current_index: int,
    *,
    months: int,
    frequency: str,
) -> int | None:
    target = _shift_months(points[current_index].period_start, -months)
    matched = exact_index.get(target)
    if matched is not None and matched < current_index:
        return matched
    # Daily and weekly official series can omit weekends or publication holidays. Use the
    # nearest prior observation only within a narrow tolerance; never jump across a long gap.
    if frequency in {"daily", "weekly"}:
        candidate = bisect_right(dates, target, hi=current_index) - 1
        tolerance = 7 if frequency == "daily" else 14
        if candidate >= 0 and 0 <= (target - dates[candidate]).days <= tolerance:
            return candidate
    return None


def transform_points(points: list[Point], transform: str, frequency: str) -> list[Point]:
    if transform == "level":
        return points
    values = [_valid_value(point) for point in points]
    dates = [point.period_start for point in points]
    exact_index = {value: index for index, value in enumerate(dates)}
    result: list[Point] = []

    for index, point in enumerate(points):
        current = values[index]
        transformed: Decimal | None = None
        if current is not None:
            lag_index: int | None = None
            if transform == "difference":
                lag_index = index - 1 if index >= 1 else None
                if lag_index is not None and values[lag_index] is not None:
                    transformed = current - values[lag_index]  # type: ignore[operator]
            elif transform == "mom":
                if frequency == "monthly":
                    lag_index = _calendar_lag_index(
                        points, dates, exact_index, index, months=1, frequency=frequency
                    )
                else:
                    lag_index = index - 1 if index >= 1 else None
                if lag_index is not None and values[lag_index] not in (None, Decimal(0)):
                    transformed = (current / values[lag_index] - 1) * 100  # type: ignore[operator]
            elif transform == "qoq":
                if frequency in {"monthly", "quarterly", "daily", "weekly"}:
                    lag_index = _calendar_lag_index(
                        points, dates, exact_index, index, months=3, frequency=frequency
                    )
                if lag_index is not None and values[lag_index] not in (None, Decimal(0)):
                    transformed = (current / values[lag_index] - 1) * 100  # type: ignore[operator]
            elif transform == "yoy":
                lag_index = _calendar_lag_index(
                    points, dates, exact_index, index, months=12, frequency=frequency
                )
                if lag_index is not None and values[lag_index] not in (None, Decimal(0)):
                    transformed = (current / values[lag_index] - 1) * 100  # type: ignore[operator]
            elif transform in {"annualized_3m", "annualized_6m"}:
                months = 3 if transform == "annualized_3m" else 6
                if frequency in {"monthly", "quarterly", "daily", "weekly"}:
                    lag_index = _calendar_lag_index(
                        points, dates, exact_index, index, months=months, frequency=frequency
                    )
                if lag_index is not None and values[lag_index] not in (None, Decimal(0)):
                    ratio = current / values[lag_index]  # type: ignore[operator]
                    transformed = (Decimal(str(float(ratio) ** (12 / months))) - 1) * 100
            elif transform == "rebased_100":
                base = next((value for value in values if value not in (None, Decimal(0))), None)
                if base is not None:
                    transformed = current / base * 100
            elif transform == "zscore":
                window = [float(v) for v in values[max(0, index - 59) : index + 1] if v is not None]
                if len(window) >= 2:
                    deviation = pstdev(window)
                    transformed = (
                        Decimal(str((float(current) - fmean(window)) / deviation))
                        if deviation
                        else Decimal(0)
                    )

        result.append(
            Point(
                period_start=point.period_start,
                period_end=point.period_end,
                value=transformed,
                value_text=None,
                status=point.status,
                published_at=point.published_at,
                vintage_at=point.vintage_at,
                source_series_id=point.source_series_id,
                run_id=point.run_id,
                publication_batch_id=point.publication_batch_id,
                raw_object_id=point.raw_object_id,
            )
        )
    return result


def correlation(
    left: list[Decimal | None], right: list[Decimal | None]
) -> tuple[float | None, int]:
    pairs = [
        (float(a), float(b))
        for a, b in zip(left, right, strict=False)
        if a is not None and b is not None
    ]
    if len(pairs) < 3:
        return None, len(pairs)
    xs = [pair[0] for pair in pairs]
    ys = [pair[1] for pair in pairs]
    mean_x = fmean(xs)
    mean_y = fmean(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in pairs)
    denominator = sqrt(sum((x - mean_x) ** 2 for x in xs) * sum((y - mean_y) ** 2 for y in ys))
    return (numerator / denominator if denominator else None), len(pairs)
