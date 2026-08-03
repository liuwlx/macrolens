from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Response

from ..dependencies import CurrentUser, CurrentWorkspace, SessionDep
from ..errors import AppError
from ..schemas import (
    ObservationResponse,
    RevisionResponse,
    SeriesAnalyticsResponse,
    SeriesBrowserResponse,
    SeriesDetail,
)
from ..services.data_browser import (
    BrowserFilters,
    browser_csv,
    series_analytics,
    series_browser,
    series_csv,
    taxonomy_descendant_ids,
)
from ..services.series import get_observations, get_revisions, get_series_detail, search_series

router = APIRouter(prefix="/series", tags=["Series"])


def _validate_date_range(start: date | None, end: date | None) -> None:
    if start and end and start > end:
        raise AppError(422, "日期范围无效", "start 必须早于或等于 end。", "invalid_date_range")


async def _browser_filters(
    session: SessionDep,
    *,
    q: str | None,
    node_id: UUID | None,
    tree_code: str,
    provider: str | None,
    theme: str | None,
    frequency: str | None,
    unit: str | None,
    seasonal_adjustment: str | None,
) -> BrowserFilters:
    node_ids = (
        await taxonomy_descendant_ids(session, tree_code, node_id) if node_id is not None else None
    )
    return BrowserFilters(
        q=q,
        node_ids=node_ids,
        provider=provider,
        theme=theme,
        frequency=frequency,
        unit=unit,
        seasonal_adjustment=seasonal_adjustment,
    )


@router.get("/browser", response_model=SeriesBrowserResponse)
async def browse_series(
    session: SessionDep,
    _user: CurrentUser,
    _workspace: CurrentWorkspace,
    q: str | None = Query(default=None, max_length=200),
    node_id: UUID | None = None,
    tree_code: str = Query(default="macro", max_length=80),
    provider: str | None = None,
    theme: str | None = None,
    frequency: str | None = None,
    unit: str | None = None,
    seasonal_adjustment: str | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
    sort: str = Query(
        default="taxonomy",
        pattern="^(taxonomy|name|current_period|current|change|period_change|yoy)$",
    ),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1_000_000),
    data_as_of: datetime | None = None,
) -> SeriesBrowserResponse:
    _validate_date_range(published_from, published_to)
    filters = await _browser_filters(
        session,
        q=q,
        node_id=node_id,
        tree_code=tree_code,
        provider=provider,
        theme=theme,
        frequency=frequency,
        unit=unit,
        seasonal_adjustment=seasonal_adjustment,
    )
    return await series_browser(
        session,
        filters=filters,
        sort=sort,  # type: ignore[arg-type]
        order=order,  # type: ignore[arg-type]
        limit=limit,
        offset=offset,
        data_as_of=data_as_of,
        published_from=published_from,
        published_to=published_to,
    )


@router.get("/browser/export")
async def export_series_browser(
    session: SessionDep,
    _user: CurrentUser,
    _workspace: CurrentWorkspace,
    q: str | None = Query(default=None, max_length=200),
    node_id: UUID | None = None,
    tree_code: str = Query(default="macro", max_length=80),
    provider: str | None = None,
    theme: str | None = None,
    frequency: str | None = None,
    unit: str | None = None,
    seasonal_adjustment: str | None = None,
    published_from: date | None = None,
    published_to: date | None = None,
    sort: str = Query(
        default="taxonomy",
        pattern="^(taxonomy|name|current_period|current|change|period_change|yoy)$",
    ),
    order: str = Query(default="asc", pattern="^(asc|desc)$"),
    data_as_of: datetime | None = None,
) -> Response:
    _validate_date_range(published_from, published_to)
    filters = await _browser_filters(
        session,
        q=q,
        node_id=node_id,
        tree_code=tree_code,
        provider=provider,
        theme=theme,
        frequency=frequency,
        unit=unit,
        seasonal_adjustment=seasonal_adjustment,
    )
    result = await series_browser(
        session,
        filters=filters,
        sort=sort,  # type: ignore[arg-type]
        order=order,  # type: ignore[arg-type]
        limit=10_000,
        offset=0,
        data_as_of=data_as_of,
        published_from=published_from,
        published_to=published_to,
    )
    return Response(
        content=browser_csv(result),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="macrolens-series-browser.csv"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{series_id}/export")
async def export_series(
    series_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    _workspace: CurrentWorkspace,
    start: date | None = None,
    end: date | None = None,
    transform: str = Query(
        default="level",
        pattern="^(level|difference|mom|qoq|yoy|annualized_3m|annualized_6m|rebased_100|zscore)$",
    ),
    data_as_of: datetime | None = None,
) -> Response:
    _validate_date_range(start, end)
    content = await series_csv(
        session,
        series_id=series_id,
        start=start,
        end=end,
        transform=transform,
        data_as_of=data_as_of,
    )
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="macrolens-series.csv"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/{series_id}/analytics", response_model=SeriesAnalyticsResponse)
async def get_series_analytics(
    series_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    _workspace: CurrentWorkspace,
    start: date | None = None,
    end: date | None = None,
    transform: str = Query(
        default="level",
        pattern="^(level|difference|mom|qoq|yoy|annualized_3m|annualized_6m|rebased_100|zscore)$",
    ),
    data_as_of: datetime | None = None,
) -> SeriesAnalyticsResponse:
    _validate_date_range(start, end)
    return await series_analytics(
        session,
        series_id=series_id,
        start=start,
        end=end,
        transform=transform,
        data_as_of=data_as_of,
    )


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
