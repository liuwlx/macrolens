from datetime import date
from decimal import Decimal

from macrolens_api.services.transforms import Point, correlation, transform_points


def point(month: int, value: str | None) -> Point:
    parsed = Decimal(value) if value is not None else None
    return Point(
        period_start=date(2024, month, 1),
        period_end=date(2024, month, 28),
        value=parsed,
        status="normal",
        published_at=None,
        vintage_at="2024-12-31T00:00:00Z",
    )


def test_difference_and_mom() -> None:
    points = [point(1, "100"), point(2, "102"), point(3, "104.04")]
    differences = transform_points(points, "difference", "monthly")
    assert differences[0].value is None
    assert differences[1].value == Decimal("2")
    monthly = transform_points(points, "mom", "monthly")
    assert monthly[1].value == Decimal("2.00")
    assert monthly[2].value == Decimal("2.00")


def test_yoy_uses_frequency_lag() -> None:
    points = [
        Point(date(2023, month, 1), date(2023, month, 28), Decimal("100"), "normal", None, "v")
        for month in range(1, 13)
    ] + [Point(date(2024, 1, 1), date(2024, 1, 28), Decimal("105"), "normal", None, "v")]
    result = transform_points(points, "yoy", "monthly")
    assert result[-1].value == Decimal("5.00")


def test_rebased_and_zscore_handle_missing_values() -> None:
    points = [point(1, None), point(2, "10"), point(3, "20")]
    rebased = transform_points(points, "rebased_100", "monthly")
    assert rebased[1].value == Decimal("100")
    assert rebased[2].value == Decimal("200")
    zscore = transform_points(points, "zscore", "monthly")
    assert zscore[0].value is None
    assert zscore[2].value is not None


def test_correlation() -> None:
    coefficient, observations = correlation(
        [Decimal("1"), Decimal("2"), Decimal("3")],
        [Decimal("2"), Decimal("4"), Decimal("6")],
    )
    assert observations == 3
    assert coefficient == 1.0


def test_mapping_transform_applies_declared_scale_factor() -> None:
    from datetime import UTC, datetime
    from decimal import Decimal
    from types import SimpleNamespace

    from macrolens_worker.providers.base import NormalizedObservation, apply_mapping_transform

    source = SimpleNamespace(
        source_locator={"scale_factor": "0.001"},
        source_frequency="weekly",
    )
    observations = [
        NormalizedObservation(
            source_series_id=1,
            period_start=date(2026, 1, 3),
            period_end=date(2026, 1, 9),
            value=Decimal("250000"),
            vintage_at=datetime(2026, 1, 10, tzinfo=UTC),
        )
    ]
    result = apply_mapping_transform(observations, source)
    assert result[0].value == Decimal("250.000")
    assert "scaled_by:0.001" in result[0].quality_flags
