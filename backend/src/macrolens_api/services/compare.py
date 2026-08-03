from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ..schemas import (
    CompareRequest,
    CompareResponse,
    CompareSeriesResult,
    CorrelationCell,
    ObservationPoint,
)
from .series import get_observations
from .transforms import correlation


async def compare_series(session: AsyncSession, request: CompareRequest) -> CompareResponse:
    results: list[CompareSeriesResult] = []
    aligned: dict[UUID, dict[object, Decimal | None]] = {}
    data_as_of = datetime.now(UTC)

    for spec in request.series:
        response = await get_observations(
            session,
            series_id=spec.series_id,
            start=request.start,
            end=request.end,
            transform=spec.transform,
            vintage=request.vintage,
        )
        data = response.data
        if spec.lag_periods:
            shifted: list[ObservationPoint] = []
            values = [point.value for point in data]
            for index, point in enumerate(data):
                source_index = index - spec.lag_periods
                value = values[source_index] if 0 <= source_index < len(values) else None
                shifted.append(point.model_copy(update={"value": value}))
            data = shifted
        results.append(
            CompareSeriesResult(
                series=response.series,
                transform=spec.transform,
                axis=spec.axis,
                lag_periods=spec.lag_periods,
                data=data,
                license=response.meta.license,
            )
        )
        aligned[spec.series_id] = {point.period_start: point.value for point in data}
        data_as_of = max(data_as_of, response.meta.data_as_of)

    correlations: list[CorrelationCell] = []
    if request.include_correlation:
        for left_index, left in enumerate(request.series):
            for right in request.series[left_index:]:
                periods = sorted(set(aligned[left.series_id]) & set(aligned[right.series_id]))
                coefficient, observations = correlation(
                    [aligned[left.series_id][period] for period in periods],
                    [aligned[right.series_id][period] for period in periods],
                )
                correlations.append(
                    CorrelationCell(
                        left_series_id=left.series_id,
                        right_series_id=right.series_id,
                        coefficient=coefficient,
                        observations=observations,
                    )
                )
    return CompareResponse(items=results, correlations=correlations, data_as_of=data_as_of)
