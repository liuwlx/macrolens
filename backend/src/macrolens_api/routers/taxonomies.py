from __future__ import annotations

from collections import defaultdict
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Path, Query
from sqlalchemy import select

from ..catalog_registry import get_catalog_registry, validate_catalog_projection
from ..config import get_settings
from ..demo_data import demo_taxonomy, demo_taxonomy_children
from ..dependencies import ReadSessionDep
from ..errors import AppError
from ..models import Series, TaxonomyNode, TaxonomySeries
from ..schemas import TaxonomyChildNode, TaxonomyChildrenResponse
from ..services.data_browser import BrowserFilters, _load_candidates, _matches, _summary

router = APIRouter(prefix="/taxonomies", tags=["Catalog"])
settings = get_settings()


def _validate_registry_tree(
    tree_code: str,
    nodes: list[TaxonomyNode],
    series_codes: set[str] | None = None,
) -> None:
    registry = get_catalog_registry()
    validate_catalog_projection(
        registry,
        tree_code=tree_code,
        nodes=((node.id, node.code, node.parent_id) for node in nodes),
        series_codes=series_codes,
    )


@router.get("/{tree_code}/children", response_model=TaxonomyChildrenResponse)
async def taxonomy_children(
    session: ReadSessionDep,
    tree_code: str = Path(min_length=1, max_length=80),
    parent_id: UUID | None = None,
    q: str | None = Query(default=None, max_length=200),
    scope: str = Query(default="children", pattern="^(children|all)$"),
    provider: str | None = None,
    theme: str | None = None,
    frequency: str | None = None,
    unit: str | None = None,
    seasonal_adjustment: str | None = None,
) -> TaxonomyChildrenResponse:
    if settings.data_mode == "demo":
        return demo_taxonomy_children(
            tree_code,
            parent_id=parent_id,
            q=q,
            scope=scope,
            provider=provider,
            theme=theme,
            frequency=frequency,
            unit=unit,
            seasonal_adjustment=seasonal_adjustment,
        )
    assert session is not None
    parsed_parent = parent_id
    nodes = list(
        (
            await session.scalars(
                select(TaxonomyNode)
                .where(TaxonomyNode.tree_code == tree_code, TaxonomyNode.visible.is_(True))
                .order_by(TaxonomyNode.sort_order, TaxonomyNode.name_zh)
            )
        ).all()
    )
    if not nodes:
        raise AppError(404, "分类树不存在", "没有找到指定分类树。", "taxonomy_not_found")
    _validate_registry_tree(tree_code, nodes)
    by_id = {node.id: node for node in nodes}
    if parsed_parent is not None and parsed_parent not in by_id:
        raise AppError(404, "分类节点不存在", "没有找到指定父节点。", "taxonomy_node_not_found")
    children: dict[UUID | None, list[TaxonomyNode]] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node)

    candidates = await _load_candidates(session)
    filters = BrowserFilters(
        q=None,
        provider=provider,
        theme=theme,
        frequency=frequency,
        unit=unit,
        seasonal_adjustment=seasonal_adjustment,
    )
    candidates = [candidate for candidate in candidates if _matches(candidate, filters)]
    series_by_node: dict[UUID, set[UUID]] = defaultdict(set)
    for candidate in candidates:
        for node_id in candidate.node_ids:
            if node_id in by_id:
                series_by_node[node_id].add(candidate.series.id)

    def descendant_nodes(node_id: UUID) -> set[UUID]:
        result = {node_id}
        pending = [(node_id, 0)]
        while pending:
            current, depth = pending.pop()
            if depth >= 64:
                raise AppError(
                    409,
                    "分类树过深",
                    "分类树超过安全遍历深度，无法完成统计。",
                    "taxonomy_depth_exceeded",
                )
            if len(result) > 10_000:
                raise AppError(
                    409,
                    "分类树过大",
                    "分类树超过安全遍历节点上限，无法完成统计。",
                    "taxonomy_size_exceeded",
                )
            for child in children[current]:
                if child.id not in result:
                    result.add(child.id)
                    pending.append((child.id, depth + 1))
        return result

    active_series_ids = {candidate.series.id for candidate in candidates}
    if q and q.strip():
        needle = q.strip().casefold()
        matching_candidates = [
            candidate
            for candidate in candidates
            if _matches(
                candidate,
                BrowserFilters(
                    q=q,
                    provider=provider,
                    theme=theme,
                    frequency=frequency,
                    unit=unit,
                    seasonal_adjustment=seasonal_adjustment,
                ),
            )
        ]
        active_series_ids = {candidate.series.id for candidate in matching_candidates}
        search_nodes = nodes if scope == "all" else children[parsed_parent]
        matching_nodes = [
            node
            for node in search_nodes
            if needle in node.code.casefold()
            or needle in node.name_zh.casefold()
            or needle in (node.name_en or "").casefold()
        ]
        for node in matching_nodes:
            for descendant_id in descendant_nodes(node.id):
                active_series_ids.update(series_by_node[descendant_id])

    visible_nodes: list[TaxonomyNode] = []
    descendant_series_by_node: dict[UUID, set[UUID]] = {}
    for node in children[parsed_parent]:
        descendants = descendant_nodes(node.id)
        descendant_series = set().union(*(series_by_node[item] for item in descendants))
        descendant_series &= active_series_ids
        if descendant_series:
            visible_nodes.append(node)
            descendant_series_by_node[node.id] = descendant_series
    response_nodes: list[TaxonomyChildNode] = []
    for node in visible_nodes:
        descendant_series = descendant_series_by_node[node.id]
        response_nodes.append(
            TaxonomyChildNode(
                id=node.id,
                code=node.code,
                name_zh=node.name_zh,
                name_en=node.name_en,
                node_type=node.node_type,
                icon_key=node.icon_key,
                has_children=bool(children[node.id]),
                direct_series_count=len(series_by_node[node.id] & active_series_ids),
                descendant_series_count=len(descendant_series),
            )
        )
    direct_series = [
        _summary(candidate, None)
        for candidate in candidates
        if (
            parsed_parent is not None
            and parsed_parent in candidate.node_ids
            and candidate.series.id in active_series_ids
        )
    ]
    direct_series.sort(key=lambda item: (item.name_zh, item.canonical_code))
    return TaxonomyChildrenResponse(
        tree_code=tree_code,
        parent_id=parsed_parent,
        nodes=response_nodes,
        series=direct_series,
        data_mode="live",
    )


@router.get("/{tree_code}")
async def taxonomy(
    tree_code: str, session: ReadSessionDep, include_series: bool = True
) -> dict[str, Any]:
    if settings.data_mode == "demo":
        return demo_taxonomy(tree_code, include_series=include_series)
    assert session is not None
    nodes = list(
        (
            await session.scalars(
                select(TaxonomyNode)
                .where(TaxonomyNode.tree_code == tree_code, TaxonomyNode.visible.is_(True))
                .order_by(TaxonomyNode.sort_order, TaxonomyNode.name_zh)
            )
        ).all()
    )
    if not nodes:
        raise AppError(404, "分类树不存在", "没有找到指定分类树。", "taxonomy_not_found")
    _validate_registry_tree(tree_code, nodes)
    series_by_node: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    if include_series and nodes:
        rows = (
            await session.execute(
                select(TaxonomySeries, Series)
                .join(Series, Series.id == TaxonomySeries.series_id)
                .where(
                    TaxonomySeries.node_id.in_([node.id for node in nodes]),
                    TaxonomySeries.is_primary.is_(True),
                )
                .order_by(TaxonomySeries.display_order, Series.name_zh)
            )
        ).all()
        _validate_registry_tree(
            tree_code,
            nodes,
            {series.canonical_code for _mapping, series in rows},
        )
        for mapping, series in rows:
            series_by_node[mapping.node_id].append(
                {
                    "id": str(series.id),
                    "canonical_code": series.canonical_code,
                    "name_zh": series.name_zh,
                    "name_en": series.name_en,
                    "frequency": series.frequency,
                    "unit": series.unit_label_zh,
                    "role": mapping.display_role,
                }
            )
    children: dict[Any, list[TaxonomyNode]] = defaultdict(list)
    for node in nodes:
        children[node.parent_id].append(node)

    def serialize(node: TaxonomyNode) -> dict[str, Any]:
        return {
            "id": str(node.id),
            "code": node.code,
            "name_zh": node.name_zh,
            "name_en": node.name_en,
            "node_type": node.node_type,
            "icon_key": node.icon_key,
            "description": node.description,
            "series": series_by_node[node.id],
            "children": [serialize(child) for child in children[node.id]],
        }

    return {
        "tree_code": tree_code,
        "nodes": [serialize(node) for node in children[None]],
        "data_mode": "live",
    }
