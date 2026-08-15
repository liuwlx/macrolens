from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from macrolens_api.models import Dataset, SourceSeries
from macrolens_worker.providers.base import NormalizedObservation


@dataclass(frozen=True, slots=True)
class CompletenessIssue:
    code: str
    message: str
    source_series_id: int | None = None
    period_start: date | None = None


DEFAULT_STALENESS_DAYS = {
    "daily": 14,
    "weekly": 28,
    "monthly": 90,
    "quarterly": 180,
    "semiannual": 300,
    "semi-annual": 300,
    "annual": 600,
}


def validate_ingestion_completeness(
    mappings: list[tuple[SourceSeries, Dataset]],
    observations: Iterable[NormalizedObservation],
    *,
    mode: str,
    now: datetime | None = None,
) -> tuple[list[CompletenessIssue], dict[str, object]]:
    current = now or datetime.now(UTC)
    expected = {source.id: source for source, _dataset in mappings}
    by_source: dict[int, list[NormalizedObservation]] = defaultdict(list)
    issues: list[CompletenessIssue] = []
    duplicate_keys: dict[tuple[int, date, datetime], NormalizedObservation] = {}

    for item in observations:
        if item.source_series_id not in expected:
            issues.append(
                CompletenessIssue(
                    "unexpected_source_series",
                    f"Adapter returned unconfigured source_series_id={item.source_series_id}",
                    item.source_series_id,
                    item.period_start,
                )
            )
            continue
        by_source[item.source_series_id].append(item)
        key = (item.source_series_id, item.period_start, item.vintage_at)
        previous = duplicate_keys.get(key)
        if previous is not None and (previous.value, previous.value_text) != (
            item.value,
            item.value_text,
        ):
            issues.append(
                CompletenessIssue(
                    "conflicting_duplicate",
                    "Two rows in the same provider snapshot disagree for the same period.",
                    item.source_series_id,
                    item.period_start,
                )
            )
        duplicate_keys[key] = item

    for source_id, source in expected.items():
        rows = sorted(
            by_source.get(source_id, []), key=lambda item: (item.period_start, item.vintage_at)
        )
        if not rows:
            issues.append(
                CompletenessIssue(
                    "mapped_series_missing",
                    f"Verified source mapping {source_id} returned no observations.",
                    source_id,
                )
            )
            continue
        latest_by_period: dict[date, NormalizedObservation] = {}
        for row in rows:
            previous = latest_by_period.get(row.period_start)
            if previous is None or row.vintage_at >= previous.vintage_at:
                latest_by_period[row.period_start] = row
        latest_rows = sorted(latest_by_period.values(), key=lambda item: item.period_start)
        non_null = [
            row for row in latest_rows if row.value is not None or row.value_text is not None
        ]
        if not non_null and not bool(source.source_locator.get("allow_all_null", False)):
            issues.append(
                CompletenessIssue(
                    "mapped_series_all_null",
                    f"Verified source mapping {source_id} returned only missing values.",
                    source_id,
                )
            )

        transform = source.source_locator.get("transform")
        allowed_leading_nulls = (
            int(source.source_locator.get("periods", 1))
            if transform == "period_difference"
            else int(source.source_locator.get("allowed_leading_null_periods", 0))
        )
        allowed_null_periods = int(source.source_locator.get("allowed_null_periods", 0))
        null_rows = [row for row in latest_rows if row.value is None and row.value_text is None]
        candidate_nulls = null_rows[allowed_leading_nulls:]
        allowed_null_dates_raw = source.source_locator.get("allowed_null_periods_by_date")
        if allowed_null_dates_raw is None:
            unexpected_nulls = candidate_nulls[allowed_null_periods:]
            allowed_nulls_description = str(allowed_null_periods)
        else:
            allowed_null_requirements = _parse_allowed_null_periods_by_date(
                allowed_null_dates_raw
            )
            if allowed_null_requirements is None:
                issues.append(
                    CompletenessIssue(
                        "invalid_allowed_null_periods",
                        f"Source {source_id} allowed_null_periods_by_date must map exact "
                        "ISO dates to non-empty required quality flags.",
                        source_id,
                    )
                )
                unexpected_nulls = candidate_nulls
                allowed_nulls_description = "no exemptions (invalid policy)"
            else:
                unexpected_nulls = [
                    row
                    for row in candidate_nulls
                    if (
                        (required_flag := allowed_null_requirements.get(row.period_start))
                        is None
                        or required_flag not in row.quality_flags
                    )
                ]
                allowed_nulls_description = str(sorted(allowed_null_requirements))
        if unexpected_nulls:
            first = unexpected_nulls[0]
            issues.append(
                CompletenessIssue(
                    "missing_observation_value",
                    f"Source {source_id} has {len(unexpected_nulls)} missing latest values; "
                    f"allowed {allowed_nulls_description} after {allowed_leading_nulls} "
                    "leading periods.",
                    source_id,
                    first.period_start,
                )
            )

        frequency = (source.source_frequency or "").lower()
        if mode in {"backfill", "vintage_backfill"}:
            expected_first_raw = source.source_locator.get("expected_first_period")
            if expected_first_raw:
                try:
                    expected_first = date.fromisoformat(str(expected_first_raw)[:10])
                except ValueError:
                    issues.append(
                        CompletenessIssue(
                            "invalid_expected_first_period",
                            f"Source {source_id} has invalid expected_first_period="
                            f"{expected_first_raw!r}.",
                            source_id,
                        )
                    )
                else:
                    # Compare the raw period boundary, including an allowed leading null
                    # created by a deterministic transform such as period_difference. Using only
                    # non-null output would falsely shift the start by one period and could also
                    # let an upstream history expansion or truncation pass unnoticed.
                    earliest = min((row.period_start for row in latest_rows), default=None)
                    if (
                        earliest is not None
                        and earliest != expected_first
                        and not bool(source.source_locator.get("allow_source_start_gap", False))
                    ):
                        issues.append(
                            CompletenessIssue(
                                "history_start_mismatch",
                                f"Source {source_id} history begins at {earliest}; "
                                f"verified first period is {expected_first}.",
                                source_id,
                                earliest,
                            )
                        )

        misaligned = [
            row.period_start
            for row in latest_rows
            if not _is_period_aligned(row.period_start, frequency)
        ]
        if misaligned:
            issues.append(
                CompletenessIssue(
                    "period_alignment",
                    f"Source {source_id} returned a {frequency} period on an invalid boundary.",
                    source_id,
                    misaligned[0],
                )
            )

        min_key = (
            "min_observations_backfill"
            if mode in {"backfill", "vintage_backfill"}
            else "min_observations_incremental"
        )
        minimum = int(
            source.source_locator.get(min_key, source.source_locator.get("min_observations", 1))
        )
        unique_periods = set(latest_by_period)
        non_null_periods = {row.period_start for row in non_null}
        if len(non_null_periods) < minimum:
            issues.append(
                CompletenessIssue(
                    "minimum_history",
                    f"Source {source_id} returned {len(non_null_periods)} non-null "
                    f"periods; expected at least {minimum}.",
                    source_id,
                )
            )
        if bool(
            source.source_locator.get(
                "require_contiguous",
                frequency
                in {"weekly", "monthly", "quarterly", "semiannual", "semi-annual", "annual"},
            )
        ):
            missing = _missing_regular_periods(unique_periods, frequency)
            allowed = int(source.source_locator.get("allowed_missing_periods", 0))
            if len(missing) > allowed:
                issues.append(
                    CompletenessIssue(
                        "history_gap",
                        f"Source {source_id} has {len(missing)} missing {frequency} "
                        f"periods; allowed {allowed}.",
                        source_id,
                        missing[0] if missing else None,
                    )
                )
        if not bool(source.source_locator.get("skip_freshness_check", False)):
            newest = (
                max(row.period_end for row in non_null)
                if non_null
                else max(row.period_end for row in latest_rows)
            )
            max_staleness = int(
                source.source_locator.get(
                    "max_staleness_days",
                    DEFAULT_STALENESS_DAYS.get(frequency, 180),
                )
            )
            if current.date() - newest > timedelta(days=max_staleness):
                issues.append(
                    CompletenessIssue(
                        "stale_latest_period",
                        f"Source {source_id} latest period {newest} is older than "
                        f"{max_staleness} days.",
                        source_id,
                        newest,
                    )
                )

    observed_ids = set(by_source)
    metrics: dict[str, object] = {
        "mapped_series_count": len(expected),
        "observed_series_count": len(observed_ids & set(expected)),
        "coverage_ratio": len(observed_ids & set(expected)) / max(1, len(expected)),
        "observation_count": sum(len(rows) for rows in by_source.values()),
        "non_null_observation_count": sum(
            1
            for rows in by_source.values()
            for row in rows
            if row.value is not None or row.value_text is not None
        ),
        "blocking_issue_count": len(issues),
    }
    return issues, metrics


def _parse_allowed_null_periods_by_date(value: object) -> dict[date, str] | None:
    if not isinstance(value, dict):
        return None
    parsed: dict[date, str] = {}
    for raw_date, required_flag in value.items():
        if not isinstance(raw_date, str) or not isinstance(required_flag, str):
            return None
        if not required_flag or required_flag != required_flag.strip():
            return None
        try:
            period = date.fromisoformat(raw_date)
        except ValueError:
            return None
        if raw_date != period.isoformat():
            return None
        parsed[period] = required_flag
    return parsed


def _missing_regular_periods(periods: set[date], frequency: str) -> list[date]:
    if len(periods) < 2:
        return []
    ordered = sorted(periods)
    expected: list[date] = []
    current = ordered[0]
    end = ordered[-1]
    while current <= end:
        expected.append(current)
        current = _next_period(current, frequency)
        if len(expected) > 100000:
            break
    return [item for item in expected if item not in periods]


def _next_period(value: date, frequency: str) -> date:
    if frequency == "weekly":
        return value + timedelta(days=7)
    months = {
        "monthly": 1,
        "quarterly": 3,
        "semiannual": 6,
        "semi-annual": 6,
        "annual": 12,
    }.get(frequency)
    if months is None:
        return value + timedelta(days=1)
    month_index = value.year * 12 + value.month - 1 + months
    return date(month_index // 12, month_index % 12 + 1, 1)


def _is_period_aligned(value: date, frequency: str) -> bool:
    if frequency in {"monthly", "quarterly", "semiannual", "semi-annual", "annual"}:
        if value.day != 1:
            return False
    if frequency == "quarterly":
        return value.month in {1, 4, 7, 10}
    if frequency in {"semiannual", "semi-annual"}:
        return value.month in {1, 7}
    if frequency == "annual":
        return value.month == 1
    return True
