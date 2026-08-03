from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AppError
from ..models import (
    Dataset,
    LicensePolicy,
    ObservationLatest,
    ObservationVintage,
    Provider,
    Series,
    SeriesAlias,
    SourceSeries,
)
from ..schemas import (
    LicenseInfo,
    LineageInfo,
    ObservationMeta,
    ObservationPoint,
    ObservationResponse,
    ProviderInfo,
    RevisionItem,
    RevisionResponse,
    SeriesDetail,
    SeriesSummary,
)
from .transforms import Point, transform_points


def _license_from_policy(policy: LicensePolicy | None, provider: Provider) -> LicenseInfo:
    if policy is None:
        public = provider.redistribution_ok
        return LicenseInfo(
            display_allowed=public,
            download_allowed=public,
            api_redistribution_allowed=public,
            ai_context_allowed=public,
            attribution_required=True,
            attribution_text=provider.attribution_text,
        )
    return LicenseInfo(
        display_allowed=policy.display_allowed,
        download_allowed=policy.download_allowed,
        api_redistribution_allowed=policy.api_redistribution_allowed,
        ai_context_allowed=policy.ai_context_allowed,
        attribution_required=policy.attribution_required,
        attribution_text=policy.attribution_text,
    )


async def get_primary_source(session: AsyncSession, series_id: UUID) -> tuple[SourceSeries, Dataset, Provider]:
    row = (
        await session.execute(
            select(SourceSeries, Dataset, Provider)
            .join(Dataset, Dataset.id == SourceSeries.dataset_id)
            .join(Provider, Provider.id == Dataset.provider_id)
            .where(
                SourceSeries.series_id == series_id,
                SourceSeries.is_primary.is_(True),
                SourceSeries.mapping_status == "verified",
            )
        )
    ).first()
    if row is None:
        raise AppError(
            404,
            "指标数据源尚未就绪",
            "该指标没有已验证的主数据源映射。",
            "source_mapping_not_ready",
        )
    return row[0], row[1], row[2]


async def get_license(
    session: AsyncSession, provider: Provider, dataset: Dataset
) -> LicenseInfo:
    today = date.today()
    policy = await session.scalar(
        select(LicensePolicy)
        .where(
            LicensePolicy.provider_id == provider.id,
            or_(LicensePolicy.dataset_id == dataset.id, LicensePolicy.dataset_id.is_(None)),
            or_(LicensePolicy.effective_from.is_(None), LicensePolicy.effective_from <= today),
            or_(LicensePolicy.effective_to.is_(None), LicensePolicy.effective_to >= today),
        )
        .order_by(LicensePolicy.dataset_id.desc().nullslast(), LicensePolicy.created_at.desc())
    )
    return _license_from_policy(policy, provider)




def _transformed_unit(transform: str, level_unit: str) -> str:
    if transform in {"level", "difference"}:
        return level_unit
    if transform == "zscore":
        return "标准差"
    if transform == "rebased_100":
        return "指数（基期=100）"
    return "%"

def _provider_info(provider: Provider) -> ProviderInfo:
    return ProviderInfo(
        code=provider.code,
        name=provider.name,
        attribution=provider.attribution_text,
        license_class=provider.license_class,
    )


async def _latest_for_source(session: AsyncSession, source_series_id: int) -> ObservationLatest | None:
    return await session.scalar(
        select(ObservationLatest)
        .where(ObservationLatest.source_series_id == source_series_id)
        .order_by(ObservationLatest.period_start.desc())
        .limit(1)
    )


async def build_series_summary(
    session: AsyncSession,
    series: Series,
    source: SourceSeries | None = None,
    provider: Provider | None = None,
    license_info: LicenseInfo | None = None,
) -> SeriesSummary:
    expose_values = license_info is None or license_info.display_allowed
    latest = await _latest_for_source(session, source.id) if source and expose_values else None
    return SeriesSummary(
        id=series.id,
        canonical_code=series.canonical_code,
        name_zh=series.name_zh,
        name_en=series.name_en,
        theme=series.theme,
        frequency=series.frequency,
        unit_code=series.unit_code,
        unit_label_zh=series.unit_label_zh,
        default_transform=series.default_transform,
        latest_period=latest.period_start if latest else (series.latest_period if expose_values else None),
        latest_value=latest.value if latest else None,
        latest_vintage_at=latest.vintage_at if latest else None,
        provider=_provider_info(provider) if provider else None,
    )


async def search_series(
    session: AsyncSession,
    *,
    q: str | None,
    theme: str | None,
    provider_code: str | None,
    frequency: str | None,
    unit: str | None,
    status: str,
    limit: int,
    offset: int,
) -> tuple[list[SeriesSummary], int]:
    filters: list[Any] = [Series.status == status]
    if q:
        pattern = f"%{q.strip()}%"
        alias_exists = select(SeriesAlias.id).where(
            SeriesAlias.series_id == Series.id, SeriesAlias.alias.ilike(pattern)
        ).exists()
        filters.append(
            or_(
                Series.name_zh.ilike(pattern),
                Series.name_en.ilike(pattern),
                Series.canonical_code.ilike(pattern),
                alias_exists,
            )
        )
    if theme:
        filters.append(Series.theme == theme)
    if frequency:
        filters.append(Series.frequency == frequency)
    if unit:
        filters.append(Series.unit_code == unit)

    source_join = and_(
        SourceSeries.series_id == Series.id,
        SourceSeries.is_primary.is_(True),
        SourceSeries.mapping_status == "verified",
    )
    stmt: Select[Any] = (
        select(Series, SourceSeries, Dataset, Provider)
        .outerjoin(SourceSeries, source_join)
        .outerjoin(Dataset, Dataset.id == SourceSeries.dataset_id)
        .outerjoin(Provider, Provider.id == Dataset.provider_id)
        .where(*filters)
    )
    if provider_code:
        stmt = stmt.where(Provider.code == provider_code)
    count_stmt = select(func.count()).select_from(stmt.order_by(None).subquery())
    total = int(await session.scalar(count_stmt) or 0)
    rows = (
        await session.execute(
            stmt.order_by(Series.theme, Series.name_zh).offset(offset).limit(limit)
        )
    ).all()
    items: list[SeriesSummary] = []
    for series, source, dataset, provider in rows:
        license_info = await get_license(session, provider, dataset) if provider and dataset else None
        items.append(await build_series_summary(session, series, source, provider, license_info))
    return items, total


async def get_series_detail(session: AsyncSession, series_id: UUID) -> SeriesDetail:
    series = await session.get(Series, series_id)
    if series is None:
        raise AppError(404, "指标不存在", "没有找到该指标。", "series_not_found")
    aliases = list(
        (
            await session.scalars(
                select(SeriesAlias.alias).where(SeriesAlias.series_id == series.id).order_by(SeriesAlias.alias)
            )
        ).all()
    )
    source: SourceSeries | None = None
    provider: Provider | None = None
    license_info: LicenseInfo | None = None
    try:
        source, dataset, provider = await get_primary_source(session, series.id)
        license_info = await get_license(session, provider, dataset)
    except AppError:
        pass
    summary = await build_series_summary(session, series, source, provider, license_info)
    return SeriesDetail(
        **summary.model_dump(),
        description=series.description,
        seasonal_adjustment=series.seasonal_adjustment,
        geography_code=series.geography_code,
        decimal_places=series.decimal_places,
        status=series.status,
        first_period=series.first_period,
        aliases=aliases,
        license=license_info,
    )


async def _query_vintage_points(
    session: AsyncSession,
    source_id: int,
    start: date | None,
    end: date | None,
    vintage: str,
) -> list[ObservationVintage]:
    stmt = select(ObservationVintage).where(ObservationVintage.source_series_id == source_id)
    if start:
        stmt = stmt.where(ObservationVintage.period_start >= start)
    if end:
        stmt = stmt.where(ObservationVintage.period_start <= end)
    if vintage == "first_release":
        stmt = stmt.distinct(ObservationVintage.period_start).order_by(
            ObservationVintage.period_start, ObservationVintage.vintage_at.asc()
        )
    else:
        try:
            as_of = datetime.fromisoformat(vintage.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AppError(422, "vintage 参数无效", "请使用 latest、first_release 或 ISO 时间。", "invalid_vintage") from exc
        stmt = (
            stmt.where(ObservationVintage.vintage_at <= as_of)
            .distinct(ObservationVintage.period_start)
            .order_by(ObservationVintage.period_start, ObservationVintage.vintage_at.desc())
        )
    rows = list((await session.scalars(stmt)).all())
    rows.sort(key=lambda row: row.period_start)
    return rows


async def get_observations(
    session: AsyncSession,
    *,
    series_id: UUID,
    start: date | None,
    end: date | None,
    transform: str,
    data_as_of: datetime,
    first_release: bool = False,
) -> ObservationResponse:
    series = await session.get(Series, series_id)
    if series is None:
        raise AppError(404, "指标不存在", "没有找到该指标。", "series_not_found")
    source, dataset, provider = await get_primary_source(session, series_id)
    license_info = await get_license(session, provider, dataset)
    if not license_info.display_allowed:
        raise AppError(403, "数据许可限制", "该数据源当前不允许在产品中展示。", "license_display_denied")

    rows: list[Any] = await _query_vintage_points(
        session,
        source.id,
        start,
        end,
        "first_release" if first_release else data_as_of.isoformat(),
    )

    points = [
        Point(
            period_start=row.period_start,
            period_end=row.period_end,
            value=row.value,
            value_text=row.value_text,
            status=row.observation_status,
            published_at=row.published_at,
            vintage_at=row.vintage_at,
        )
        for row in rows
    ]
    transformed = transform_points(points, transform, series.frequency)
    latest_point = next((point for point in reversed(points) if point.value is not None), None)
    summary = SeriesSummary(
        id=series.id,
        canonical_code=series.canonical_code,
        name_zh=series.name_zh,
        name_en=series.name_en,
        theme=series.theme,
        frequency=series.frequency,
        unit_code=series.unit_code,
        unit_label_zh=series.unit_label_zh,
        default_transform=series.default_transform,
        latest_period=latest_point.period_start if latest_point else None,
        latest_value=latest_point.value if latest_point else None,
        latest_vintage_at=(
            latest_point.vintage_at
            if latest_point and isinstance(latest_point.vintage_at, datetime)
            else None
        ),
        provider=_provider_info(provider),
    )
    return ObservationResponse(
        series=summary,
        data=[
            ObservationPoint(
                period_start=point.period_start,
                period_end=point.period_end,
                value=point.value,
                value_text=point.value_text,
                status=point.status,
                published_at=point.published_at,  # type: ignore[arg-type]
                vintage_at=point.vintage_at,  # type: ignore[arg-type]
            )
            for point in transformed
        ],
        meta=ObservationMeta(
            data_as_of=data_as_of,  # type: ignore[arg-type]
            vintage="first_release" if first_release else data_as_of.isoformat(),
            transform=transform,
            frequency=series.frequency,
            unit=_transformed_unit(transform, series.unit_label_zh),
            lineage=LineageInfo(
                provider=provider.code,
                dataset=dataset.code,
                provider_series_id=source.provider_series_id,
                source_series_id=source.id,
                source_locator=source.source_locator,
            ),
            license=license_info,
        ),
    )


async def get_revisions(
    session: AsyncSession,
    *,
    series_id: UUID,
    start: date | None,
    end: date | None,
    data_as_of: datetime,
) -> RevisionResponse:
    source, dataset, provider = await get_primary_source(session, series_id)
    license_info = await get_license(session, provider, dataset)
    if not license_info.display_allowed:
        raise AppError(403, "数据许可限制", "该数据源当前不允许在产品中展示修订历史。", "license_display_denied")
    stmt = select(ObservationVintage).where(
        ObservationVintage.source_series_id == source.id,
        ObservationVintage.vintage_at <= data_as_of,
    )
    if start:
        stmt = stmt.where(ObservationVintage.period_start >= start)
    if end:
        stmt = stmt.where(ObservationVintage.period_start <= end)
    rows = list(
        (
            await session.scalars(
                stmt.order_by(ObservationVintage.period_start, ObservationVintage.vintage_at)
            )
        ).all()
    )
    grouped: dict[date, list[ObservationVintage]] = {}
    for row in rows:
        grouped.setdefault(row.period_start, []).append(row)
    items: list[RevisionItem] = []
    for period, versions in grouped.items():
        first = versions[0]
        latest = versions[-1]
        revision: Decimal | None = None
        if first.value is not None and latest.value is not None:
            revision = latest.value - first.value
        items.append(
            RevisionItem(
                period_start=period,
                first_value=first.value,
                latest_value=latest.value,
                revision=revision,
                first_vintage_at=first.vintage_at,
                latest_vintage_at=latest.vintage_at,
                versions=len(versions),
            )
        )
    return RevisionResponse(series_id=series_id, items=items, data_as_of=data_as_of)
