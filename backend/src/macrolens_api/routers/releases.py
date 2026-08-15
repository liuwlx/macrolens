from __future__ import annotations

from datetime import UTC, date, datetime, time
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from ..dependencies import SessionDep
from ..errors import AppError
from ..models import (
    ForecastSnapshot,
    MarketReaction,
    Provider,
    ReleaseDefinition,
    ReleaseEvent,
    ReleaseEventSeries,
    Series,
)
from ..schemas import (
    ForecastItem,
    MarketReactionItem,
    ReleaseEventDetail,
    ReleaseEventSummary,
    ReleaseMetric,
)
from ..services.licenses import get_license_for_provider

router = APIRouter(prefix="/release-events", tags=["Releases"])


async def _visible_forecasts(
    session: SessionDep, rows: list[tuple[ForecastSnapshot, Provider]]
) -> list[ForecastItem]:
    items: list[ForecastItem] = []
    for forecast, provider in rows:
        license_info = await get_license_for_provider(session, provider.id)
        if not license_info.display_allowed:
            continue
        items.append(
            ForecastItem(
                observed_at=forecast.observed_at,
                consensus_value=forecast.consensus_value,
                median_value=forecast.median_value,
                high_value=forecast.high_value,
                low_value=forecast.low_value,
                respondent_count=forecast.respondent_count,
                provider_code=provider.code,
            )
        )
    return items


async def _visible_market_reactions(
    session: SessionDep, rows: list[tuple[MarketReaction, Provider | None]]
) -> list[MarketReactionItem]:
    items: list[MarketReactionItem] = []
    for reaction, provider in rows:
        # Market reactions must have source lineage. Provider-less rows are not safe to publish.
        if provider is None:
            continue
        license_info = await get_license_for_provider(session, provider.id)
        if not license_info.display_allowed:
            continue
        items.append(
            MarketReactionItem(
                instrument_code=reaction.instrument_code,
                window_code=reaction.window_code,
                absolute_change=reaction.absolute_change,
                percent_change=reaction.percent_change,
                observed_at=reaction.observed_at,
            )
        )
    return items


async def _event_summary(
    session: SessionDep, event: ReleaseEvent, definition: ReleaseDefinition, provider: Provider
) -> ReleaseEventSummary:
    metric_rows = (
        await session.execute(
            select(ReleaseEventSeries, Series)
            .join(Series, Series.id == ReleaseEventSeries.series_id)
            .where(ReleaseEventSeries.event_id == event.id)
        )
    ).all()
    forecast_rows = (
        (
            await session.execute(
                select(ForecastSnapshot, Provider)
                .join(Provider, Provider.id == ForecastSnapshot.provider_id)
                .where(ForecastSnapshot.event_id == event.id)
                .order_by(ForecastSnapshot.observed_at.desc())
            )
        )
        .tuples()
        .all()
    )
    visible_forecasts = await _visible_forecasts(session, list(forecast_rows))
    latest_forecast = visible_forecasts[0] if visible_forecasts else None
    return ReleaseEventSummary(
        id=event.id,
        title_zh=event.title_zh,
        title_en=event.title_en,
        country_code=event.country_code,
        reference_period=event.reference_period,
        scheduled_at=event.scheduled_at,
        actual_released_at=event.actual_released_at,
        status=event.status,
        importance_score=event.importance_score,
        release_type=definition.release_type,
        provider_code=provider.code,
        provider_name=provider.name,
        official_url=event.official_url,
        metrics=[
            ReleaseMetric(
                series_id=series.id,
                name_zh=series.name_zh,
                transform=mapping.transform_code,
                actual_value=mapping.actual_value,
                previous_value=mapping.previous_value,
                revised_previous_value=mapping.revised_previous_value,
                unit_label=mapping.unit_label,
            )
            for mapping, series in metric_rows
        ],
        consensus_value=latest_forecast.consensus_value if latest_forecast else None,
    )


@router.get("")
async def list_events(
    session: SessionDep,
    start: date,
    end: date,
    country: str = "US",
    type: str | None = None,  # noqa: A002
    importance_min: int | None = Query(default=None, ge=1, le=5),
    provider: str | None = None,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    if start > end:
        raise AppError(422, "日期范围无效", "start 必须早于或等于 end。", "invalid_date_range")
    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end, time.max, tzinfo=UTC)
    stmt = (
        select(ReleaseEvent, ReleaseDefinition, Provider)
        .join(ReleaseDefinition, ReleaseDefinition.id == ReleaseEvent.release_definition_id)
        .join(Provider, Provider.id == ReleaseDefinition.provider_id)
        .where(
            ReleaseEvent.scheduled_at >= start_dt,
            ReleaseEvent.scheduled_at <= end_dt,
            ReleaseEvent.country_code == country,
        )
    )
    if type:
        stmt = stmt.where(ReleaseDefinition.release_type == type)
    if importance_min:
        stmt = stmt.where(ReleaseEvent.importance_score >= importance_min)
    if provider:
        stmt = stmt.where(Provider.code == provider)
    if status:
        stmt = stmt.where(ReleaseEvent.status == status)
    total = int(
        await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    )
    rows = (
        await session.execute(stmt.order_by(ReleaseEvent.scheduled_at).offset(offset).limit(limit))
    ).all()
    items = [
        await _event_summary(session, event, definition, source)
        for event, definition, source in rows
    ]
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{event_id}", response_model=ReleaseEventDetail)
async def event_detail(event_id: UUID, session: SessionDep) -> ReleaseEventDetail:
    row = (
        await session.execute(
            select(ReleaseEvent, ReleaseDefinition, Provider)
            .join(ReleaseDefinition, ReleaseDefinition.id == ReleaseEvent.release_definition_id)
            .join(Provider, Provider.id == ReleaseDefinition.provider_id)
            .where(ReleaseEvent.id == event_id)
        )
    ).first()
    if row is None:
        raise AppError(404, "发布事件不存在", "没有找到该发布事件。", "release_event_not_found")
    event, definition, provider = row
    summary = await _event_summary(session, event, definition, provider)
    forecast_rows = (
        (
            await session.execute(
                select(ForecastSnapshot, Provider)
                .join(Provider, Provider.id == ForecastSnapshot.provider_id)
                .where(ForecastSnapshot.event_id == event_id)
                .order_by(ForecastSnapshot.observed_at.desc())
            )
        )
        .tuples()
        .all()
    )
    reaction_rows = (
        (
            await session.execute(
                select(MarketReaction, Provider)
                .outerjoin(Provider, Provider.id == MarketReaction.data_provider_id)
                .where(MarketReaction.event_id == event_id)
                .order_by(MarketReaction.instrument_code, MarketReaction.window_code)
            )
        )
        .tuples()
        .all()
    )
    visible_forecasts = await _visible_forecasts(session, list(forecast_rows))
    visible_reactions = await _visible_market_reactions(session, list(reaction_rows))
    return ReleaseEventDetail(
        **summary.model_dump(),
        source_timezone=event.source_timezone,
        forecasts=visible_forecasts,
        market_reactions=visible_reactions,
    )


@router.get("/{event_id}/forecasts", response_model=list[ForecastItem])
async def event_forecasts(event_id: UUID, session: SessionDep) -> list[ForecastItem]:
    exists = await session.get(ReleaseEvent, event_id)
    if exists is None:
        raise AppError(404, "发布事件不存在", "没有找到该发布事件。", "release_event_not_found")
    rows = (
        (
            await session.execute(
                select(ForecastSnapshot, Provider)
                .join(Provider, Provider.id == ForecastSnapshot.provider_id)
                .where(ForecastSnapshot.event_id == event_id)
                .order_by(ForecastSnapshot.observed_at.desc())
            )
        )
        .tuples()
        .all()
    )
    return await _visible_forecasts(session, list(rows))


@router.get("/{event_id}/market-reactions", response_model=list[MarketReactionItem])
async def event_market_reactions(event_id: UUID, session: SessionDep) -> list[MarketReactionItem]:
    exists = await session.get(ReleaseEvent, event_id)
    if exists is None:
        raise AppError(404, "发布事件不存在", "没有找到该发布事件。", "release_event_not_found")
    rows = (
        (
            await session.execute(
                select(MarketReaction, Provider)
                .outerjoin(Provider, Provider.id == MarketReaction.data_provider_id)
                .where(MarketReaction.event_id == event_id)
                .order_by(MarketReaction.instrument_code, MarketReaction.window_code)
            )
        )
        .tuples()
        .all()
    )
    return await _visible_market_reactions(session, list(rows))
