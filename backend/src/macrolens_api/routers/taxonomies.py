from __future__ import annotations

from collections import defaultdict
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from ..dependencies import SessionDep
from ..models import Series, TaxonomyNode, TaxonomySeries

router = APIRouter(prefix="/taxonomies", tags=["Catalog"])


@router.get("/{tree_code}")
async def taxonomy(tree_code: str, session: SessionDep, include_series: bool = True) -> dict[str, Any]:
    nodes = list(
        (
            await session.scalars(
                select(TaxonomyNode)
                .where(TaxonomyNode.tree_code == tree_code, TaxonomyNode.visible.is_(True))
                .order_by(TaxonomyNode.sort_order, TaxonomyNode.name_zh)
            )
        ).all()
    )
    series_by_node: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    if include_series and nodes:
        rows = (
            await session.execute(
                select(TaxonomySeries, Series)
                .join(Series, Series.id == TaxonomySeries.series_id)
                .where(TaxonomySeries.node_id.in_([node.id for node in nodes]), Series.status == "active")
                .order_by(TaxonomySeries.display_order, Series.name_zh)
            )
        ).all()
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

    return {"tree_code": tree_code, "nodes": [serialize(node) for node in children[None]]}
