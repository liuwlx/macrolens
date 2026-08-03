from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query

from ..dependencies import SessionDep
from ..errors import AppError
from ..schemas import ObservationResponse, RevisionResponse, SeriesDetail, SeriesSummary
from ..services.series import get_observations, get_revisions, get_series_detail, search_series

router = APIRouter(prefix="/series", tags=["Series"])


def _validate_date_range(start: date | None, end: date | None) -> None:
    if start and end and start > end:
        raise AppError(422, "日期范围无效", "start 必须早于或等于 end。", "invalid_date_range")


@router.get("")
async def list_series(
    session: SessionDep,
    q: str | None = Query(default=None, max_length=200),
    theme: str | None = None,
    provider: str | None = None,
    frequency: str | None = None,
    unit: str | None = None,
    status: str = "active",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    items, total = await search_series(
        session,
        q=q,
        theme=theme,
        provider_code=provider,
        frequency=frequency,
        unit=unit,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {"items": [item.model_dump(mode="json") for item in items], "total": total, "limit": limit, "offset": offset}


@router.get("/{series_id}", response_model=SeriesDetail)
async def series_detail(series_id: UUID, session: SessionDep) -> SeriesDetail:
    return await get_series_detail(session, series_id)


@router.get("/{series_id}/observations", response_model=ObservationResponse)
async def series_observations(
    series_id: UUID,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    transform: str = Query(
        default="level",
        pattern="^(level|difference|mom|qoq|yoy|annualized_3m|annualized_6m|rebased_100|zscore)$",
    ),
    vintage: str = "latest",
) -> ObservationResponse:
    _validate_date_range(start, end)
    return await get_observations(
        session,
        series_id=series_id,
        start=start,
        end=end,
        transform=transform,
        vintage=vintage,
    )


@router.get("/{series_id}/revisions", response_model=RevisionResponse)
async def series_revisions(
    series_id: UUID,
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
) -> RevisionResponse:
    _validate_date_range(start, end)
    return await get_revisions(session, series_id=series_id, start=start, end=end)
