from __future__ import annotations

import csv
import io
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from statistics import median, pstdev
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import Date as SQLDate
from sqlalchemy import and_, case, cast, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..catalog_registry import get_catalog_registry
from ..config import get_settings
from ..errors import AppError
from ..models import (
    Dataset,
    DerivedDefinition,
    LicensePolicy,
    ObservationVintage,
    Provider,
    ReleaseDefinition,
    ReleaseEvent,
    ReleaseEventSeries,
    Series,
    SeriesAlias,
    SeriesDependency,
    SourceSeries,
    TaxonomyNode,
    TaxonomySeries,
)
from ..schemas import (
    AICapabilityResponse,
    BrowserFacets,
    BrowserFacetValue,
    BrowserMetric,
    BrowserObservation,
    BrowserPagination,
    CapabilityStatus,
    ContributionComponent,
    ContributionPeriod,
    ContributionResult,
    LicenseInfo,
    NextRelease,
    ProviderInfo,
    SeriesAnalyticsResponse,
    SeriesAvailability,
    SeriesBrowserItem,
    SeriesBrowserResponse,
    SeriesCapabilities,
    SeriesStatistics,
    SeriesSummary,
)
from .series import _license_from_policy
from .transforms import Point, transform_points

BrowserSort = Literal[
    "taxonomy", "name", "current_period", "current", "change", "period_change", "yoy"
]
BrowserOrder = Literal["asc", "desc"]
FACET_NAMES = ("provider", "theme", "frequency", "unit", "seasonal_adjustment")


@dataclass(slots=True)
class SourceBinding:
    source: SourceSeries
    dataset: Dataset
    provider: Provider


@dataclass(slots=True)
class BrowserCandidate:
    series: Series
    sources: dict[int, SourceBinding] = field(default_factory=dict)
    catalog_sources: dict[int, SourceBinding] = field(default_factory=dict)
    node_ids: set[UUID] = field(default_factory=set)
    node_codes: set[str] = field(default_factory=set)
    taxonomy_order: int = 2_147_483_647
    aliases: list[str] = field(default_factory=list)

    @property
    def source_status(self) -> Literal["ready", "missing", "conflict"]:
        if len(self.sources) == 1:
            return "ready"
        return "missing" if not self.sources else "conflict"

    @property
    def binding(self) -> SourceBinding | None:
        return next(iter(self.sources.values())) if len(self.sources) == 1 else None

    @property
    def catalog_binding(self) -> SourceBinding | None:
        if len(self.catalog_sources) == 1:
            return next(iter(self.catalog_sources.values()))
        return self.binding


@dataclass(frozen=True, slots=True)
class BrowserFilters:
    q: str | None = None
    node_ids: frozenset[UUID] | None = None
    provider: str | None = None
    theme: str | None = None
    frequency: str | None = None
    unit: str | None = None
    seasonal_adjustment: str | None = None


def normalize_data_as_of(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        normalized = value.replace(tzinfo=UTC)
    else:
        normalized = value.astimezone(UTC)
    if normalized > datetime.now(UTC):
        raise AppError(
            422,
            "快照时间无效",
            "data_as_of 不能晚于请求开始时间。",
            "invalid_data_as_of",
        )
    return normalized


def _deny_by_default(provider: Provider) -> LicenseInfo:
    """Return the non-leaking result for missing or ambiguous effective policy."""
    return LicenseInfo(
        display_allowed=False,
        download_allowed=False,
        api_redistribution_allowed=False,
        ai_context_allowed=False,
        attribution_required=True,
        attribution_text=provider.attribution_text,
    )


def _source_reason(candidate: BrowserCandidate) -> tuple[str | None, str | None]:
    if candidate.source_status == "missing":
        return "source_mapping_not_ready", "该指标没有唯一且已验证的主数据源。"
    if candidate.source_status == "conflict":
        return "source_mapping_conflict", "该指标存在多个已验证主数据源，无法确定统一口径。"
    return None, None


def _summary(
    candidate: BrowserCandidate,
    current: Point | None,
) -> SeriesSummary:
    binding = candidate.catalog_binding
    provider = binding.provider if binding else None
    series = candidate.series
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
        latest_period=current.period_start if current else None,
        latest_value=current.value if current else None,
        latest_vintage_at=(
            current.vintage_at if current and isinstance(current.vintage_at, datetime) else None
        ),
        provider=(
            ProviderInfo(
                code=provider.code,
                name=provider.name,
                attribution=provider.attribution_text,
                license_class=provider.license_class,
            )
            if provider
            else None
        ),
    )


def _unavailable_metric(
    unit: str,
    reason_code: str,
    reason: str,
    *,
    basis: str | None = None,
) -> BrowserMetric:
    return BrowserMetric(
        value=None,
        unit=unit,
        status="unavailable",
        basis=basis,
        reason_code=reason_code,
        reason=reason,
    )


def _round_value(value: Decimal | None, decimal_places: int) -> Decimal | None:
    if value is None:
        return None
    quantum = Decimal(1).scaleb(-max(decimal_places, 0))
    return value.quantize(quantum)


def _absolute_change_unit(series: Series) -> str:
    text = f"{series.unit_code} {series.unit_label_zh}".lower()
    is_rate = any(token in text for token in ("percent", "percentage", "%", "率"))
    return "pp" if is_rate else series.unit_label_zh


def _period_transform(frequency: str) -> tuple[str, str]:
    return {
        "daily": ("mom", "dod"),
        "weekly": ("mom", "wow"),
        "monthly": ("mom", "mom"),
        "quarterly": ("qoq", "qoq"),
        "annual": ("yoy", "yoy"),
    }.get(frequency, ("mom", "period"))


def build_browser_item(
    candidate: BrowserCandidate,
    points: list[Point],
    license_info: LicenseInfo | None,
    availability: SeriesAvailability | None = None,
) -> SeriesBrowserItem:
    series = candidate.series
    reason_code, reason = _source_reason(candidate)
    availability_reason = (
        {
            "pending_mapping": ("source_mapping_not_ready", "官方来源映射尚未完成。"),
            "pending_credentials": ("source_credentials_not_ready", "采集凭据尚未配置。"),
            "pending_license": ("source_license_not_ready", "许可或法务审核尚未完成。"),
            "not_ingested": ("source_not_ingested", "该指标尚未采集观测数据。"),
            "not_available_as_of": (
                "source_not_available_as_of",
                "该指标在所选数据快照时点尚不可用。",
            ),
        }.get(availability)
        if availability is not None
        else None
    )
    if availability_reason is not None:
        reason_code, reason = availability_reason
    display_denied = license_info is not None and not license_info.display_allowed
    if display_denied:
        reason_code, reason = "license_display_denied", "当前许可策略不允许展示该指标数值。"
    visible_points = (
        [] if display_denied else [point for point in points if point.value is not None]
    )
    current = visible_points[-1] if visible_points else None
    previous = visible_points[-2] if len(visible_points) > 1 else None
    change_unit = _absolute_change_unit(series)
    if current is None or previous is None:
        missing_code = reason_code or "insufficient_history"
        missing_reason = reason or "至少需要两个有效观测点。"
        change = _unavailable_metric(change_unit, missing_code, missing_reason)
    else:
        assert current.value is not None and previous.value is not None
        change = BrowserMetric(
            value=_round_value(current.value - previous.value, series.decimal_places + 1),
            unit=change_unit,
            status="available",
        )

    period_transform, basis = _period_transform(series.frequency)
    period_points = transform_points(points, period_transform, series.frequency) if points else []
    period_value = period_points[-1].value if period_points else None
    if display_denied or period_value is None:
        period_change = _unavailable_metric(
            "%",
            reason_code or "period_change_unavailable",
            reason or "缺少可计算期间变化的有效基期，或基期值为零。",
            basis=basis,
        )
    else:
        period_change = BrowserMetric(
            value=_round_value(period_value, series.decimal_places + 1),
            unit="%",
            basis=basis,
            status="available",
        )

    yoy_points = transform_points(points, "yoy", series.frequency) if points else []
    yoy_value = yoy_points[-1].value if yoy_points else None
    if display_denied or yoy_value is None:
        yoy = _unavailable_metric(
            "%",
            reason_code or "yoy_unavailable",
            reason or "缺少同比基期、基期值为零或历史长度不足。",
            basis="yoy",
        )
    else:
        yoy = BrowserMetric(
            value=_round_value(yoy_value, series.decimal_places + 1),
            unit="%",
            basis="yoy",
            status="available",
        )

    def observation(point: Point | None) -> BrowserObservation | None:
        if point is None or not isinstance(point.vintage_at, datetime):
            return None
        return BrowserObservation(
            period_start=point.period_start,
            period_end=point.period_end,
            value=_round_value(point.value, series.decimal_places),
            published_at=point.published_at if isinstance(point.published_at, datetime) else None,
            vintage_at=point.vintage_at,
        )

    return SeriesBrowserItem(
        series=_summary(candidate, current),
        current=observation(current),
        previous=observation(previous),
        change=change,
        period_change=period_change,
        yoy=yoy,
        license=license_info,
        display_denied=display_denied,
        source_status=candidate.source_status,
        unavailable_reason_code=reason_code,
        taxonomy_order=candidate.taxonomy_order,
        availability=availability or ("available" if current is not None else "not_ingested"),
    )


async def _load_candidates(
    session: AsyncSession,
    *,
    series_id: UUID | None = None,
) -> list[BrowserCandidate]:
    registry = get_catalog_registry()
    catalog_codes = tuple(indicator.canonical_code for indicator in registry.indicators)
    source_join = SourceSeries.series_id == Series.id
    statement = (
        select(Series, SourceSeries, Dataset, Provider, TaxonomySeries, TaxonomyNode)
        .outerjoin(SourceSeries, source_join)
        .outerjoin(Dataset, Dataset.id == SourceSeries.dataset_id)
        .outerjoin(Provider, Provider.id == Dataset.provider_id)
        .join(
            TaxonomySeries,
            (TaxonomySeries.series_id == Series.id) & TaxonomySeries.is_primary.is_(True),
        )
        .join(
            TaxonomyNode,
            (TaxonomyNode.id == TaxonomySeries.node_id)
            & (TaxonomyNode.tree_code == registry.tree_code)
            & TaxonomyNode.visible.is_(True),
        )
        .where(Series.canonical_code.in_(catalog_codes))
    )
    if series_id is not None:
        statement = statement.where(Series.id == series_id)
    rows = (await session.execute(statement)).all()
    by_id: dict[UUID, BrowserCandidate] = {}
    for series, source, dataset, provider, taxonomy, taxonomy_node in rows:
        candidate = by_id.setdefault(series.id, BrowserCandidate(series=series))
        if source is not None and dataset is not None and provider is not None:
            binding = SourceBinding(source, dataset, provider)
            candidate.catalog_sources[source.id] = binding
            if source.is_primary and source.mapping_status == "verified":
                candidate.sources[source.id] = binding
        if taxonomy is not None:
            candidate.node_ids.add(taxonomy.node_id)
            candidate.node_codes.add(taxonomy_node.code)
            candidate.taxonomy_order = min(candidate.taxonomy_order, taxonomy.display_order)
    if by_id:
        aliases = (
            await session.execute(
                select(SeriesAlias.series_id, SeriesAlias.alias).where(
                    SeriesAlias.series_id.in_(list(by_id))
                )
            )
        ).all()
        for candidate_id, alias in aliases:
            by_id[candidate_id].aliases.append(alias)
    if series_id is None:
        actual_codes = {candidate.series.canonical_code for candidate in by_id.values()}
        expected_codes = set(catalog_codes)
        ownership_mismatches = sum(
            candidate.node_codes
            != {registry.owner_by_series_code[candidate.series.canonical_code].code}
            for candidate in by_id.values()
            if candidate.series.canonical_code in registry.owner_by_series_code
        )
        if actual_codes != expected_codes or ownership_mismatches:
            raise AppError(
                503,
                "指标目录尚未就绪",
                "Live 指标目录与受控 registry 不一致，已停止返回部分目录。",
                "catalog_registry_mismatch",
                {
                    "expected_count": len(expected_codes),
                    "actual_count": len(actual_codes),
                    "missing_count": len(expected_codes - actual_codes),
                    "unexpected_count": len(actual_codes - expected_codes),
                    "ownership_mismatch_count": ownership_mismatches,
                },
            )
    return list(by_id.values())


async def taxonomy_descendant_ids(
    session: AsyncSession,
    tree_code: str,
    node_id: UUID,
) -> frozenset[UUID]:
    nodes = list(
        (
            await session.scalars(
                select(TaxonomyNode).where(
                    TaxonomyNode.tree_code == tree_code,
                    TaxonomyNode.visible.is_(True),
                )
            )
        ).all()
    )
    if not any(node.id == node_id for node in nodes):
        raise AppError(404, "分类节点不存在", "没有找到指定的分类节点。", "taxonomy_node_not_found")
    children: dict[UUID | None, list[UUID]] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node.id)
    result: set[UUID] = set()
    pending = [(node_id, 0)]
    while pending:
        current, depth = pending.pop()
        if current in result:
            continue
        if depth >= 64:
            raise AppError(
                409,
                "分类树过深",
                "分类树超过安全遍历深度，无法完成筛选。",
                "taxonomy_depth_exceeded",
            )
        if len(result) >= 10_000:
            raise AppError(
                409,
                "分类树过大",
                "分类树超过安全遍历节点上限，无法完成筛选。",
                "taxonomy_size_exceeded",
            )
        result.add(current)
        pending.extend((child, depth + 1) for child in children[current])
    return frozenset(result)


def _matches(candidate: BrowserCandidate, filters: BrowserFilters, skip: str | None = None) -> bool:
    series = candidate.series
    binding = candidate.catalog_binding
    if filters.node_ids is not None and not (candidate.node_ids & filters.node_ids):
        return False
    if filters.q:
        needle = filters.q.strip().casefold()
        haystack = [series.canonical_code, series.name_zh, series.name_en or "", *candidate.aliases]
        if needle and not any(needle in value.casefold() for value in haystack):
            return False
    if skip != "provider" and filters.provider:
        if binding is None or binding.provider.code != filters.provider:
            return False
    if skip != "theme" and filters.theme and series.theme != filters.theme:
        return False
    if skip != "frequency" and filters.frequency and series.frequency != filters.frequency:
        return False
    if skip != "unit" and filters.unit and series.unit_code != filters.unit:
        return False
    if (
        skip != "seasonal_adjustment"
        and filters.seasonal_adjustment
        and series.seasonal_adjustment != filters.seasonal_adjustment
    ):
        return False
    return True


def _search_rank(candidate: BrowserCandidate, q: str | None) -> tuple[int, int, str, str]:
    series = candidate.series
    if not q or not q.strip():
        return candidate.taxonomy_order, 0, series.name_zh.casefold(), series.canonical_code
    needle = q.strip().casefold()
    code = series.canonical_code.casefold()
    if code == needle:
        rank = 0
    elif code.startswith(needle):
        rank = 1
    elif needle in series.name_zh.casefold() or needle in (series.name_en or "").casefold():
        rank = 2
    elif any(needle in alias.casefold() for alias in candidate.aliases):
        rank = 3
    else:
        rank = 4
    return rank, candidate.taxonomy_order, series.name_zh.casefold(), code


def build_facets(candidates: list[BrowserCandidate], filters: BrowserFilters) -> BrowserFacets:
    values: dict[str, list[BrowserFacetValue]] = {}
    for facet in FACET_NAMES:
        counter: Counter[str] = Counter()
        for candidate in candidates:
            if not _matches(candidate, filters, skip=facet):
                continue
            binding = candidate.catalog_binding
            raw = {
                "provider": binding.provider.code if binding else "",
                "theme": candidate.series.theme,
                "frequency": candidate.series.frequency,
                "unit": candidate.series.unit_code,
                "seasonal_adjustment": candidate.series.seasonal_adjustment,
            }[facet]
            if raw:
                counter[raw] += 1
        values[facet] = [
            BrowserFacetValue(value=value, label=value, count=count)
            for value, count in sorted(counter.items())
        ]
    return BrowserFacets(**values)


async def _license_map(
    session: AsyncSession,
    bindings: list[SourceBinding],
) -> dict[int, LicenseInfo]:
    if not bindings:
        return {}
    today = date.today()
    provider_ids = {binding.provider.id for binding in bindings}
    dataset_ids = {binding.dataset.id for binding in bindings}
    policies = list(
        (
            await session.scalars(
                select(LicensePolicy)
                .where(
                    LicensePolicy.provider_id.in_(provider_ids),
                    or_(
                        LicensePolicy.dataset_id.in_(dataset_ids),
                        LicensePolicy.dataset_id.is_(None),
                    ),
                    or_(
                        LicensePolicy.effective_from.is_(None),
                        LicensePolicy.effective_from <= today,
                    ),
                    or_(LicensePolicy.effective_to.is_(None), LicensePolicy.effective_to >= today),
                )
                .order_by(LicensePolicy.created_at.desc())
            )
        ).all()
    )
    by_provider_dataset: dict[tuple[int, int | None], list[LicensePolicy]] = defaultdict(list)
    for policy in policies:
        by_provider_dataset[(policy.provider_id, policy.dataset_id)].append(policy)

    result: dict[int, LicenseInfo] = {}
    for binding in bindings:
        exact = by_provider_dataset[(binding.provider.id, binding.dataset.id)]
        fallback = by_provider_dataset[(binding.provider.id, None)]
        selected = exact if exact else fallback
        # No policy or multiple effective policies at the selected precedence layer are both
        # configuration errors. They must not inherit Provider.redistribution_ok.
        result[binding.source.id] = (
            _license_from_policy(selected[0], binding.provider)
            if len(selected) == 1
            else _deny_by_default(binding.provider)
        )
    return result


async def _points_by_source(
    session: AsyncSession,
    source_ids: set[int],
    *,
    data_as_of: datetime,
    max_points: int = 420,
) -> dict[int, list[Point]]:
    if not source_ids:
        return {}
    versioned = (
        select(
            ObservationVintage.source_series_id.label("source_id"),
            ObservationVintage.period_start,
            ObservationVintage.period_end,
            ObservationVintage.value,
            ObservationVintage.value_text,
            ObservationVintage.observation_status,
            ObservationVintage.published_at,
            ObservationVintage.vintage_at,
            func.row_number()
            .over(
                partition_by=(
                    ObservationVintage.source_series_id,
                    ObservationVintage.period_start,
                ),
                order_by=ObservationVintage.vintage_at.desc(),
            )
            .label("vintage_rank"),
        )
        .where(
            ObservationVintage.source_series_id.in_(source_ids),
            ObservationVintage.vintage_at <= data_as_of,
        )
        .subquery()
    )
    ranked = (
        select(
            versioned.c.source_id,
            versioned.c.period_start,
            versioned.c.period_end,
            versioned.c.value,
            versioned.c.value_text,
            versioned.c.observation_status,
            versioned.c.published_at,
            versioned.c.vintage_at,
            func.row_number()
            .over(
                partition_by=versioned.c.source_id,
                order_by=versioned.c.period_start.desc(),
            )
            .label("period_rank"),
        )
        .where(versioned.c.vintage_rank == 1)
        .subquery()
    )
    rows = (
        await session.execute(
            select(ranked)
            .where(ranked.c.period_rank <= max_points)
            .order_by(ranked.c.source_id, ranked.c.period_start)
        )
    ).mappings()
    grouped: dict[int, list[Point]] = defaultdict(list)
    for row in rows:
        grouped[int(row["source_id"])].append(
            Point(
                period_start=row["period_start"],
                period_end=row["period_end"],
                value=row["value"],
                value_text=row["value_text"],
                status=row["observation_status"],
                published_at=row["published_at"],
                vintage_at=row["vintage_at"],
            )
        )
    return dict(grouped)


async def _earliest_vintage_by_source(
    session: AsyncSession,
    source_ids: set[int],
) -> dict[int, datetime]:
    if not source_ids:
        return {}
    rows = (
        await session.execute(
            select(
                ObservationVintage.source_series_id,
                func.min(ObservationVintage.vintage_at),
            )
            .where(ObservationVintage.source_series_id.in_(source_ids))
            .group_by(ObservationVintage.source_series_id)
        )
    ).all()
    return {
        int(source_id): earliest for source_id, earliest in rows if isinstance(earliest, datetime)
    }


async def _lifetime_availability_by_source(
    session: AsyncSession,
    source_ids: set[int],
    *,
    data_as_of: datetime,
) -> dict[int, SeriesAvailability]:
    earliest = await _earliest_vintage_by_source(session, source_ids)
    return {
        source_id: (
            "not_available_as_of"
            if source_id in earliest and earliest[source_id] > data_as_of
            else "not_ingested"
        )
        for source_id in source_ids
    }


def _provider_credentials_ready(provider_code: str) -> bool:
    settings = get_settings()
    required_credentials = {
        "BEA_API": settings.bea_api_key,
        "CENSUS_EITS_API": settings.census_api_key,
        "EIA_API_V2": settings.eia_api_key,
        "FRED_API": settings.fred_api_key,
    }
    return provider_code not in required_credentials or bool(required_credentials[provider_code])


def _catalog_availability(
    candidate: BrowserCandidate,
    points: list[Point],
    license_info: LicenseInfo | None,
    lifetime_availability: SeriesAvailability,
) -> SeriesAvailability:
    binding = candidate.binding
    if binding is None:
        catalog_binding = candidate.catalog_binding
        if (
            catalog_binding is not None
            and catalog_binding.source.mapping_status == "license_required"
        ):
            return "pending_license"
        return "pending_mapping"
    if license_info is None or not license_info.display_allowed:
        return "pending_license"
    if points:
        return "available"
    if lifetime_availability == "not_available_as_of":
        return lifetime_availability
    if not _provider_credentials_ready(binding.provider.code):
        return "pending_credentials"
    return lifetime_availability


async def _latest_publications_by_source(
    session: AsyncSession,
    source_ids: set[int],
    *,
    data_as_of: datetime,
) -> dict[int, datetime | None]:
    if not source_ids:
        return {}
    ranked = (
        select(
            ObservationVintage.source_series_id.label("source_id"),
            ObservationVintage.published_at,
            func.row_number()
            .over(
                partition_by=ObservationVintage.source_series_id,
                order_by=(
                    ObservationVintage.period_start.desc(),
                    ObservationVintage.vintage_at.desc(),
                ),
            )
            .label("rank"),
        )
        .where(
            ObservationVintage.source_series_id.in_(source_ids),
            ObservationVintage.vintage_at <= data_as_of,
        )
        .subquery()
    )
    rows = (
        await session.execute(
            select(ranked.c.source_id, ranked.c.published_at).where(ranked.c.rank == 1)
        )
    ).all()
    return {int(source_id): published_at for source_id, published_at in rows}


async def _sort_points_by_source(
    session: AsyncSession,
    candidates: list[BrowserCandidate],
    *,
    data_as_of: datetime,
) -> dict[int, list[Point]]:
    """Load only current, previous and calendar-lag points needed by browser sort metrics."""
    bindings = [binding for candidate in candidates if (binding := candidate.binding) is not None]
    if not bindings:
        return {}
    source_ids = {binding.source.id for binding in bindings}
    versioned = (
        select(
            ObservationVintage.source_series_id.label("source_id"),
            ObservationVintage.period_start,
            ObservationVintage.period_end,
            ObservationVintage.value,
            ObservationVintage.value_text,
            ObservationVintage.observation_status,
            ObservationVintage.published_at,
            ObservationVintage.vintage_at,
            func.row_number()
            .over(
                partition_by=(
                    ObservationVintage.source_series_id,
                    ObservationVintage.period_start,
                ),
                order_by=ObservationVintage.vintage_at.desc(),
            )
            .label("vintage_rank"),
        )
        .where(
            ObservationVintage.source_series_id.in_(source_ids),
            ObservationVintage.vintage_at <= data_as_of,
        )
        .subquery()
    )
    ranked = (
        select(
            versioned.c.source_id,
            versioned.c.period_start,
            versioned.c.period_end,
            versioned.c.value,
            versioned.c.value_text,
            versioned.c.observation_status,
            versioned.c.published_at,
            versioned.c.vintage_at,
            func.row_number()
            .over(
                partition_by=versioned.c.source_id,
                order_by=versioned.c.period_start.desc(),
            )
            .label("period_rank"),
        )
        .where(versioned.c.vintage_rank == 1, versioned.c.value.is_not(None))
        .subquery()
    )
    current = (
        select(
            ranked.c.source_id,
            ranked.c.period_start.label("current_period"),
        )
        .where(ranked.c.period_rank == 1)
        .subquery()
    )
    conditions = [ranked.c.period_rank <= 2]

    def add_calendar_target(
        selected_ids: set[int],
        *,
        months: int,
        tolerance_days: int = 0,
    ) -> None:
        if not selected_ids:
            return
        interval_unit = "month" if months == 1 else "months"
        target = cast(
            current.c.current_period - text(f"INTERVAL '{months} {interval_unit}'"),
            SQLDate,
        )
        period_match = (
            ranked.c.period_start == target
            if tolerance_days == 0
            else and_(
                ranked.c.period_start <= target,
                ranked.c.period_start >= target - tolerance_days,
            )
        )
        conditions.append(and_(ranked.c.source_id.in_(selected_ids), period_match))

    by_frequency: dict[str, set[int]] = defaultdict(set)
    for candidate in candidates:
        if candidate.binding is not None:
            by_frequency[candidate.series.frequency].add(candidate.binding.source.id)
    add_calendar_target(by_frequency["monthly"], months=1)
    add_calendar_target(by_frequency["quarterly"], months=3)
    add_calendar_target(source_ids - by_frequency["daily"] - by_frequency["weekly"], months=12)
    add_calendar_target(by_frequency["daily"], months=12, tolerance_days=7)
    add_calendar_target(by_frequency["weekly"], months=12, tolerance_days=14)

    rows = (
        await session.execute(
            select(ranked)
            .join(current, current.c.source_id == ranked.c.source_id)
            .where(or_(*conditions))
            .order_by(ranked.c.source_id, ranked.c.period_start)
        )
    ).mappings()
    grouped: dict[int, list[Point]] = defaultdict(list)
    for row in rows:
        grouped[int(row["source_id"])].append(
            Point(
                period_start=row["period_start"],
                period_end=row["period_end"],
                value=row["value"],
                value_text=row["value_text"],
                status=row["observation_status"],
                published_at=row["published_at"],
                vintage_at=row["vintage_at"],
            )
        )
    return dict(grouped)


def _sort_candidates_by_metric(
    candidates: list[BrowserCandidate],
    points_by_source: dict[int, list[Point]],
    license_by_source: dict[int, LicenseInfo],
    sort: BrowserSort,
    order: BrowserOrder,
) -> list[BrowserCandidate]:
    getter: dict[str, Callable[[SeriesBrowserItem], Any]] = {
        "current_period": lambda item: item.current.period_start if item.current else None,
        "current": lambda item: item.current.value if item.current else None,
        "change": lambda item: item.change.value,
        "period_change": lambda item: item.period_change.value,
        "yoy": lambda item: item.yoy.value,
    }
    metric = getter[sort]
    decorated: list[tuple[BrowserCandidate, Any]] = []
    for candidate in candidates:
        binding = candidate.binding
        item = build_browser_item(
            candidate,
            points_by_source.get(binding.source.id, []) if binding else [],
            license_by_source.get(binding.source.id) if binding else None,
        )
        decorated.append((candidate, metric(item)))
    decorated.sort(
        key=lambda pair: (
            pair[0].taxonomy_order,
            pair[0].series.name_zh.casefold(),
            pair[0].series.canonical_code,
            str(pair[0].series.id),
        )
    )
    available = [pair for pair in decorated if pair[1] is not None]
    missing = [pair for pair in decorated if pair[1] is None]
    available.sort(key=lambda pair: pair[1], reverse=order == "desc")
    return [candidate for candidate, _value in available + missing]


async def series_browser(
    session: AsyncSession,
    *,
    filters: BrowserFilters,
    sort: BrowserSort,
    order: BrowserOrder,
    limit: int,
    offset: int,
    data_as_of: datetime | None,
    published_from: date | None,
    published_to: date | None,
) -> SeriesBrowserResponse:
    snapshot = normalize_data_as_of(data_as_of)
    candidates = await _load_candidates(session)
    facets = build_facets(candidates, filters)
    matched = [candidate for candidate in candidates if _matches(candidate, filters)]
    publication_bindings = [
        binding for candidate in matched if (binding := candidate.binding) is not None
    ]
    publication_source_ids = {binding.source.id for binding in publication_bindings}
    publications: dict[int, datetime | None] = {}
    if published_from is not None or published_to is not None:
        publications = await _latest_publications_by_source(
            session,
            publication_source_ids,
            data_as_of=snapshot,
        )

        def publication_matches(candidate: BrowserCandidate) -> bool:
            binding = candidate.binding
            published = publications.get(binding.source.id) if binding is not None else None
            if published is None:
                return False
            published_date = published.date()
            return (published_from is None or published_date >= published_from) and (
                published_to is None or published_date <= published_to
            )

        matched = [candidate for candidate in matched if publication_matches(candidate)]

    all_bindings = [binding for candidate in matched if (binding := candidate.binding) is not None]
    all_license_by_source: dict[int, LicenseInfo] | None = None
    if sort in {"current_period", "current", "change", "period_change", "yoy"}:
        all_license_by_source = await _license_map(session, all_bindings)
        sort_points = await _sort_points_by_source(
            session,
            matched,
            data_as_of=snapshot,
        )
        matched = _sort_candidates_by_metric(
            matched,
            sort_points,
            all_license_by_source,
            sort,
            order,
        )
    elif sort == "name":
        matched.sort(
            key=lambda candidate: (
                candidate.series.name_zh.casefold(),
                candidate.series.canonical_code,
                str(candidate.series.id),
            ),
            reverse=order == "desc",
        )
    else:
        matched.sort(
            key=lambda candidate: (*_search_rank(candidate, filters.q), str(candidate.series.id)),
            reverse=order == "desc",
        )

    total = len(matched)
    page = matched[offset : offset + limit]
    bindings = [binding for candidate in page if (binding := candidate.binding) is not None]
    license_by_source = (
        all_license_by_source
        if all_license_by_source is not None
        else await _license_map(session, bindings)
    )
    page_source_ids = {binding.source.id for binding in bindings}
    points = await _points_by_source(session, page_source_ids, data_as_of=snapshot)
    empty_source_ids = {source_id for source_id in page_source_ids if not points.get(source_id)}
    availability_by_source = await _lifetime_availability_by_source(
        session,
        empty_source_ids,
        data_as_of=snapshot,
    )
    items = [
        build_browser_item(
            candidate,
            points.get(candidate.binding.source.id, []) if candidate.binding else [],
            license_by_source.get(candidate.binding.source.id) if candidate.binding else None,
            _catalog_availability(
                candidate,
                points.get(candidate.binding.source.id, []) if candidate.binding else [],
                license_by_source.get(candidate.binding.source.id) if candidate.binding else None,
                (
                    availability_by_source.get(candidate.binding.source.id, "not_ingested")
                    if candidate.binding
                    else "not_ingested"
                ),
            ),
        )
        for candidate in page
    ]
    return SeriesBrowserResponse(
        items=items,
        facets=facets,
        pagination=BrowserPagination(total=total, limit=limit, offset=offset),
        data_as_of=snapshot,
        data_mode="live",
    )


def _csv_safe(value: object) -> str:
    """Neutralize spreadsheet formulas and keep a cell on a single CSV record."""
    text = str(value)
    dangerous_leading_control = text.startswith(("\t", "\r", "\n"))
    text = text.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    if dangerous_leading_control or text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def browser_csv(response: SeriesBrowserResponse) -> bytes:
    if response.pagination.total > 10_000:
        raise AppError(
            413,
            "导出数据过多",
            "浏览器导出最多允许 10,000 个指标，请缩小筛选范围。",
            "export_limit_exceeded",
        )
    restricted = [
        item for item in response.items if item.license is None or not item.license.download_allowed
    ]
    if restricted:
        raise AppError(
            403,
            "导出受许可证限制",
            "导出集合中至少有一个指标不允许下载，未生成部分文件。",
            "license_download_denied",
            {
                "restricted_total": len(restricted),
                "restricted_series": [item.series.name_zh for item in restricted[:10]],
            },
        )
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "series_id",
            "canonical_code",
            "name_zh",
            "provider",
            "frequency",
            "unit",
            "current_period",
            "current_value",
            "previous_value",
            "change",
            "period_change",
            "yoy",
            "data_as_of",
            "data_mode",
        ]
    )
    for item in response.items:
        writer.writerow(
            [
                item.series.id,
                _csv_safe(item.series.canonical_code),
                _csv_safe(item.series.name_zh),
                _csv_safe(item.series.provider.code if item.series.provider else ""),
                _csv_safe(item.series.frequency),
                _csv_safe(item.series.unit_label_zh),
                item.current.period_start if item.current else "",
                item.current.value if item.current else "",
                item.previous.value if item.previous else "",
                item.change.value if item.change.value is not None else "",
                item.period_change.value if item.period_change.value is not None else "",
                item.yoy.value if item.yoy.value is not None else "",
                response.data_as_of.isoformat(),
                response.data_mode,
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


async def series_csv(
    session: AsyncSession,
    *,
    series_id: UUID,
    start: date | None,
    end: date | None,
    transform: str,
    data_as_of: datetime | None,
) -> bytes:
    candidates = await _load_candidates(session, series_id=series_id)
    if not candidates:
        raise AppError(404, "指标不存在", "没有找到该指标。", "series_not_found")
    candidate = candidates[0]
    reason_code, reason = _source_reason(candidate)
    if candidate.binding is None:
        raise AppError(
            409,
            "指标数据源不可用",
            reason or "主数据源不可用。",
            reason_code or "source_unavailable",
        )
    binding = candidate.binding
    license_info = (await _license_map(session, [binding]))[binding.source.id]
    # Complete authorization before constructing the CSV buffer, so denied exports never produce
    # a partial response.
    if not license_info.download_allowed:
        raise AppError(
            403,
            "导出受许可证限制",
            "当前许可策略不允许下载该指标。",
            "license_download_denied",
            {"restricted_total": 1, "restricted_series": [candidate.series.name_zh]},
        )
    snapshot = normalize_data_as_of(data_as_of)
    snapshot_points = (
        await _points_by_source(
            session,
            {binding.source.id},
            data_as_of=snapshot,
            max_points=10_001,
        )
    ).get(binding.source.id, [])
    if data_as_of is not None and not snapshot_points:
        earliest = await _earliest_vintage_by_source(session, {binding.source.id})
        if earliest.get(binding.source.id, snapshot) > snapshot:
            raise AppError(
                409,
                "快照不可用",
                "指定 data_as_of 无法复现该指标的观测。",
                "snapshot_unavailable",
                {"data_as_of": snapshot.isoformat()},
            )
    points = snapshot_points
    points = [
        point
        for point in points
        if (start is None or point.period_start >= start)
        and (end is None or point.period_start <= end)
    ]
    if len(points) > 10_000:
        raise AppError(
            413,
            "导出数据过多",
            "单次指标导出最多允许 10,000 个观测点，请缩小日期范围。",
            "export_limit_exceeded",
        )
    transformed = transform_points(points, transform, candidate.series.frequency)
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "series_id",
            "canonical_code",
            "name_zh",
            "period_start",
            "period_end",
            "value",
            "status",
            "published_at",
            "vintage_at",
            "data_as_of",
            "data_mode",
            "transform",
            "unit",
            "provider",
            "attribution",
        ]
    )
    for point in transformed:
        writer.writerow(
            [
                candidate.series.id,
                _csv_safe(candidate.series.canonical_code),
                _csv_safe(candidate.series.name_zh),
                point.period_start,
                point.period_end,
                point.value if point.value is not None else "",
                _csv_safe(point.status),
                point.published_at.isoformat() if isinstance(point.published_at, datetime) else "",
                point.vintage_at.isoformat() if isinstance(point.vintage_at, datetime) else "",
                snapshot.isoformat(),
                "live",
                _csv_safe(transform),
                _csv_safe(candidate.series.unit_label_zh),
                _csv_safe(binding.provider.code),
                _csv_safe(license_info.attribution_text or binding.provider.attribution_text or ""),
            ]
        )
    return ("\ufeff" + output.getvalue()).encode("utf-8")


def _capability(allowed: bool, reason_code: str | None, reason: str | None) -> CapabilityStatus:
    return CapabilityStatus(
        allowed=allowed,
        reason_code=None if allowed else reason_code,
        reason=None if allowed else reason,
    )


def _statistics(points: list[Point], decimal_places: int) -> SeriesStatistics:
    values = [point.value for point in points if point.value is not None]
    if not values:
        return SeriesStatistics(
            count=0,
            mean=None,
            median=None,
            min=None,
            max=None,
            stddev=None,
            current_percentile=None,
        )
    current = values[-1]
    percentile = (
        Decimal(sum(1 for value in values if value <= current)) / Decimal(len(values)) * 100
    )
    return SeriesStatistics(
        count=len(values),
        mean=_round_value(sum(values) / Decimal(len(values)), decimal_places + 1),
        median=_round_value(Decimal(median(values)), decimal_places + 1),
        min=_round_value(min(values), decimal_places),
        max=_round_value(max(values), decimal_places),
        stddev=(
            _round_value(
                Decimal(str(pstdev([float(value) for value in values]))),
                decimal_places + 1,
            )
            if len(values) > 1
            else Decimal(0)
        ),
        current_percentile=_round_value(percentile, 1),
    )


async def _next_release(session: AsyncSession, series_id: UUID) -> NextRelease | None:
    role_order = case(
        (ReleaseEventSeries.role == "headline", 0),
        (ReleaseEventSeries.role == "component", 1),
        else_=2,
    )
    row = (
        await session.execute(
            select(ReleaseEvent, ReleaseEventSeries, ReleaseDefinition)
            .join(ReleaseEventSeries, ReleaseEventSeries.event_id == ReleaseEvent.id)
            .join(ReleaseDefinition, ReleaseDefinition.id == ReleaseEvent.release_definition_id)
            .where(
                ReleaseEventSeries.series_id == series_id,
                ReleaseEvent.scheduled_at >= datetime.now(UTC),
            )
            .order_by(ReleaseEvent.scheduled_at, role_order)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    event, mapping, definition = row
    return NextRelease(
        id=event.id,
        title_zh=event.title_zh,
        title_en=event.title_en,
        scheduled_at=event.scheduled_at,
        source_timezone=event.source_timezone or definition.source_timezone,
        status=event.status,
        role=mapping.role,
    )


def _contribution_unavailable(code: str, reason: str) -> ContributionResult:
    return ContributionResult(available=False, reason_code=code, reason=reason)


async def _contributions(
    session: AsyncSession,
    candidate: BrowserCandidate,
    target_points: list[Point],
    *,
    start: date | None,
    end: date | None,
    data_as_of: datetime,
) -> ContributionResult:
    # The current schema does not bind SeriesDependency rows to a specific
    # DerivedDefinition/formula_version. Without that provenance, combining a definition with
    # dependencies could silently mix versions. Fail closed until a versioned foreign key exists;
    # in particular, never interpret or execute weight_expression.
    return _contribution_unavailable(
        "contribution_version_binding_unavailable",
        "当前依赖记录未绑定贡献定义版本，无法安全提供贡献分析。",
    )

    # Kept unreachable intentionally until the schema can prove definition/dependency binding.
    definitions = list(
        (
            await session.scalars(
                select(DerivedDefinition).where(
                    DerivedDefinition.series_id == candidate.series.id,
                    DerivedDefinition.effective_from <= data_as_of.date(),
                    or_(
                        DerivedDefinition.effective_to.is_(None),
                        DerivedDefinition.effective_to >= data_as_of.date(),
                    ),
                )
            )
        ).all()
    )
    if not definitions:
        return _contribution_unavailable(
            "contribution_definition_missing", "该指标在当前快照没有生效的贡献定义。"
        )
    if len(definitions) != 1:
        return _contribution_unavailable(
            "contribution_definition_conflict", "当前快照存在多个贡献定义版本。"
        )
    definition = definitions[0]
    parameters = definition.parameters or {}
    transform = parameters.get("target_transform")
    tolerance_raw = parameters.get("reconciliation_tolerance")
    if not isinstance(transform, str) or tolerance_raw is None:
        return _contribution_unavailable(
            "contribution_parameters_missing", "贡献定义缺少目标变换或 reconciliation tolerance。"
        )
    try:
        tolerance = Decimal(str(tolerance_raw))
    except InvalidOperation:
        return _contribution_unavailable(
            "contribution_parameters_invalid", "贡献定义的 reconciliation tolerance 无效。"
        )
    dependencies = list(
        (
            await session.scalars(
                select(SeriesDependency).where(
                    SeriesDependency.derived_series_id == candidate.series.id,
                    SeriesDependency.dependency_role == "contribution",
                )
            )
        ).all()
    )
    if not dependencies:
        return _contribution_unavailable(
            "contribution_components_missing", "贡献定义没有已物化的 contribution 依赖。"
        )
    component_ids = {dependency.source_series_id for dependency in dependencies}
    component_candidates = await _load_candidates(session)
    by_id = {
        item.series.id: item for item in component_candidates if item.series.id in component_ids
    }
    if set(by_id) != component_ids or any(item.binding is None for item in by_id.values()):
        return _contribution_unavailable(
            "contribution_components_missing", "至少一个贡献组件缺少唯一已验证主数据源。"
        )
    bindings = [item.binding for item in by_id.values() if item.binding is not None]
    licenses = await _license_map(session, bindings)
    if any(not licenses[binding.source.id].display_allowed for binding in bindings):
        return _contribution_unavailable(
            "contribution_license_denied", "至少一个贡献组件不允许展示。"
        )
    points_by_source = await _points_by_source(
        session,
        {binding.source.id for binding in bindings},
        data_as_of=data_as_of,
    )
    component_values: dict[UUID, dict[date, Decimal]] = {}
    for component_id, component in by_id.items():
        binding = component.binding
        assert binding is not None
        component_values[component_id] = {
            point.period_start: point.value
            for point in points_by_source.get(binding.source.id, [])
            if point.value is not None
            and (start is None or point.period_start >= start)
            and (end is None or point.period_start <= end)
        }
    transformed_target = transform_points(target_points, transform, candidate.series.frequency)
    target_values = {
        point.period_start: point.value
        for point in transformed_target
        if point.value is not None
        and (start is None or point.period_start >= start)
        and (end is None or point.period_start <= end)
    }
    common_periods = set(target_values)
    for values in component_values.values():
        common_periods &= set(values)
    if not common_periods:
        return _contribution_unavailable(
            "contribution_observations_missing", "目标或组件在所选范围内没有共同完整期。"
        )
    period = max(common_periods)
    raw_components = [
        ContributionComponent(
            series_id=component_id,
            name_zh=by_id[component_id].series.name_zh,
            value=component_values[component_id][period],
            unit=candidate.series.unit_label_zh,
        )
        for component_id in sorted(component_ids, key=lambda value: by_id[value].series.name_zh)
    ]
    raw_components.sort(key=lambda item: abs(item.value), reverse=True)
    if len(raw_components) > 8:
        other_value = sum((item.value for item in raw_components[8:]), Decimal(0))
        components = raw_components[:8] + [
            ContributionComponent(
                series_id=None,
                name_zh="其他",
                value=other_value,
                unit=candidate.series.unit_label_zh,
                grouped=True,
            )
        ]
    else:
        components = raw_components
    contribution_total = sum((item.value for item in raw_components), Decimal(0))
    target_value = target_values[period]
    difference = contribution_total - target_value
    if abs(difference) > tolerance:
        return _contribution_unavailable(
            "contribution_reconciliation_failed", "组件贡献之和未在声明容差内与目标值对账。"
        )
    period_result = ContributionPeriod(
        period_start=period,
        target_value=target_value,
        contribution_total=contribution_total,
        difference=difference,
        components=components,
    )
    return ContributionResult(
        available=True,
        target_unit=candidate.series.unit_label_zh,
        periods=[period_result],
        components=components,
        reconciliation={"passed": True, "tolerance": tolerance, "difference": difference},
    )


async def series_analytics(
    session: AsyncSession,
    *,
    series_id: UUID,
    start: date | None,
    end: date | None,
    transform: str,
    data_as_of: datetime | None,
) -> SeriesAnalyticsResponse:
    candidates = await _load_candidates(session, series_id=series_id)
    if not candidates:
        raise AppError(404, "指标不存在", "没有找到该指标。", "series_not_found")
    candidate = candidates[0]
    reason_code, reason = _source_reason(candidate)
    if candidate.binding is None:
        raise AppError(
            409,
            "指标数据源不可用",
            reason or "主数据源不可用。",
            reason_code or "source_unavailable",
        )
    binding = candidate.binding
    license_info = (await _license_map(session, [binding]))[binding.source.id]
    if not license_info.display_allowed:
        raise AppError(
            403,
            "数据许可限制",
            "该数据源当前不允许展示分析结果。",
            "license_display_denied",
        )
    snapshot = normalize_data_as_of(data_as_of)
    snapshot_points = (
        await _points_by_source(
            session,
            {binding.source.id},
            data_as_of=snapshot,
            max_points=10_000,
        )
    ).get(binding.source.id, [])
    if data_as_of is not None and not snapshot_points:
        earliest = await _earliest_vintage_by_source(session, {binding.source.id})
        if earliest.get(binding.source.id, snapshot) > snapshot:
            raise AppError(
                409,
                "快照不可用",
                "指定 data_as_of 无法复现该指标的观测。",
                "snapshot_unavailable",
                {"data_as_of": snapshot.isoformat()},
            )
    points = snapshot_points
    points = [
        point
        for point in points
        if (start is None or point.period_start >= start)
        and (end is None or point.period_start <= end)
    ]
    transformed = transform_points(points, transform, candidate.series.frequency)
    contributions = await _contributions(
        session,
        candidate,
        points,
        start=start,
        end=end,
        data_as_of=snapshot,
    )
    display = _capability(True, None, None)
    download = _capability(
        license_info.download_allowed,
        "license_download_denied",
        "当前许可策略不允许下载。",
    )
    ai = _capability(
        license_info.ai_context_allowed,
        "license_ai_denied",
        "当前许可策略不允许用于 AI 上下文。",
    )
    contribution_capability = _capability(
        contributions.available,
        contributions.reason_code,
        contributions.reason,
    )
    capabilities = SeriesCapabilities(
        display=display,
        download=download,
        ai=ai,
        trend=display,
        history=display,
        revisions=display,
        documents=display,
        contributions=contribution_capability,
    )
    latest = next((point for point in reversed(points) if point.value is not None), None)
    return SeriesAnalyticsResponse(
        series=_summary(candidate, latest),
        statistics=_statistics(transformed, candidate.series.decimal_places),
        next_release=await _next_release(session, series_id),
        contributions=contributions,
        capabilities=capabilities,
        data_as_of=snapshot,
        data_mode="live",
    )


async def ai_capability(
    session: AsyncSession,
    *,
    series_id: UUID,
    configured: bool,
) -> AICapabilityResponse:
    candidates = await _load_candidates(session, series_id=series_id)
    if not candidates:
        raise AppError(404, "指标不存在", "没有找到该指标。", "series_not_found")
    candidate = candidates[0]
    reason_code, reason = _source_reason(candidate)
    if candidate.binding is None:
        return AICapabilityResponse(
            series_id=series_id,
            configured=configured,
            allowed=False,
            reason_code=reason_code,
            reason=reason,
        )
    license_info = (await _license_map(session, [candidate.binding]))[candidate.binding.source.id]
    if not configured:
        return AICapabilityResponse(
            series_id=series_id,
            configured=False,
            allowed=False,
            reason_code="ai_not_configured",
            reason="AI 模型尚未配置。",
        )
    if not license_info.display_allowed or not license_info.ai_context_allowed:
        return AICapabilityResponse(
            series_id=series_id,
            configured=True,
            allowed=False,
            reason_code="license_ai_denied",
            reason="当前许可策略不允许该指标进入 AI 上下文。",
        )
    return AICapabilityResponse(series_id=series_id, configured=True, allowed=True)
