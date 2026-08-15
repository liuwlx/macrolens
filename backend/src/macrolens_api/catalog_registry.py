from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Hashable, Iterable, Mapping
from collections.abc import Set as AbstractSet
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path
from typing import Any

from .errors import AppError


@dataclass(frozen=True, slots=True)
class CatalogIndicator:
    canonical_code: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CatalogTaxonomyNode:
    code: str
    parent_code: str | None
    name_zh: str
    name_en: str | None
    node_type: str
    sort_order: int
    series_codes: tuple[str, ...]
    icon_key: str | None = None


@dataclass(frozen=True)
class CatalogRegistry:
    tree_code: str
    expected_series_count: int
    indicators: tuple[CatalogIndicator, ...]
    nodes: tuple[CatalogTaxonomyNode, ...]

    @cached_property
    def nodes_by_code(self) -> dict[str, CatalogTaxonomyNode]:
        return {node.code: node for node in self.nodes}

    @cached_property
    def children_by_code(self) -> dict[str | None, tuple[CatalogTaxonomyNode, ...]]:
        grouped: dict[str | None, list[CatalogTaxonomyNode]] = defaultdict(list)
        for node in self.nodes:
            grouped[node.parent_code].append(node)
        return {
            parent: tuple(sorted(children, key=lambda item: (item.sort_order, item.code)))
            for parent, children in grouped.items()
        }

    @cached_property
    def owner_by_series_code(self) -> dict[str, CatalogTaxonomyNode]:
        return {canonical_code: node for node in self.nodes for canonical_code in node.series_codes}

    def node_path(self, node: CatalogTaxonomyNode) -> tuple[str, ...]:
        path = [node.code]
        current = node
        while current.parent_code is not None:
            current = self.nodes_by_code[current.parent_code]
            path.append(current.code)
        return tuple(reversed(path))

    @property
    def max_depth(self) -> int:
        return max(len(self.node_path(node)) - 1 for node in self.nodes)

    def path_for(self, canonical_code: str) -> tuple[str, ...]:
        return self.node_path(self.owner_by_series_code[canonical_code])

    def descendant_series_codes(self, node_code: str) -> tuple[str, ...]:
        result: list[str] = []
        pending = [self.nodes_by_code[node_code]]
        while pending:
            node = pending.pop()
            result.extend(node.series_codes)
            pending.extend(reversed(self.children_by_code.get(node.code, ())))
        return tuple(result)


CatalogNodeFact = tuple[Hashable, str, Hashable | None]


def validate_catalog_projection(
    registry: CatalogRegistry,
    *,
    tree_code: str,
    nodes: Iterable[CatalogNodeFact],
    series_codes: AbstractSet[str] | None = None,
    series_owners: Mapping[str, AbstractSet[str]] | None = None,
) -> None:
    if tree_code != registry.tree_code:
        return
    node_facts = list(nodes)
    expected_nodes = {node.code for node in registry.nodes}
    actual_node_codes_by_id = {node_id: code for node_id, code, _parent_id in node_facts}
    actual_nodes = set(actual_node_codes_by_id.values())
    actual_parents = {
        code: actual_node_codes_by_id.get(parent_id) if parent_id is not None else None
        for _node_id, code, parent_id in node_facts
    }
    expected_parents = {node.code: node.parent_code for node in registry.nodes}
    expected_series = {indicator.canonical_code for indicator in registry.indicators}
    actual_series = set(series_owners) if series_owners is not None else series_codes
    ownership_mismatch_count = 0
    if series_owners is not None:
        ownership_mismatch_count = sum(
            set(series_owners.get(canonical_code, ()))
            != {registry.owner_by_series_code[canonical_code].code}
            for canonical_code in expected_series
        )
    if (
        len(actual_node_codes_by_id) != len(node_facts)
        or len(actual_nodes) != len(node_facts)
        or actual_nodes != expected_nodes
        or actual_parents != expected_parents
        or (actual_series is not None and actual_series != expected_series)
        or ownership_mismatch_count
    ):
        raise AppError(
            503,
            "指标目录尚未就绪",
            "Live 指标目录与受控 registry 不一致，已停止返回部分或错误目录。",
            "catalog_registry_mismatch",
            {
                "expected_node_count": len(expected_nodes),
                "actual_node_count": len(actual_nodes),
                "expected_series_count": len(expected_series),
                "actual_series_count": len(actual_series) if actual_series is not None else None,
                "ownership_mismatch_count": ownership_mismatch_count,
            },
        )


def _repo_root() -> Path:
    candidates = (Path("/app"), Path(__file__).resolve().parents[3])
    for candidate in candidates:
        if (candidate / "database/seed/source_registry.json").is_file():
            return candidate
    raise RuntimeError("Cannot locate MacroLens catalog registries")


def load_catalog_registry(root: Path) -> CatalogRegistry:
    source_payload = json.loads(
        (root / "database/seed/source_registry.json").read_text(encoding="utf-8")
    )
    taxonomy_payload = json.loads(
        (root / "database/seed/taxonomy_registry.json").read_text(encoding="utf-8")
    )
    source_items = source_payload.get("indicators")
    node_items = taxonomy_payload.get("nodes")
    if not isinstance(source_items, list) or not isinstance(node_items, list):
        raise RuntimeError("Catalog registries must contain indicators and nodes lists")

    expected = int(taxonomy_payload.get("expected_series_count", -1))
    declared = int(source_payload.get("indicator_count", -1))
    indicators = tuple(
        CatalogIndicator(canonical_code=str(item["canonical_code"]), payload=dict(item))
        for item in source_items
    )
    source_codes = [indicator.canonical_code for indicator in indicators]
    if expected != 61 or declared != expected:
        raise RuntimeError("Catalog registries must declare exactly 61 indicators")
    if len(source_codes) != expected or len(set(source_codes)) != expected:
        raise RuntimeError("Source registry must contain exactly 61 unique canonical codes")

    nodes = tuple(
        CatalogTaxonomyNode(
            code=str(item["code"]),
            parent_code=str(item["parent_code"]) if item.get("parent_code") is not None else None,
            name_zh=str(item["name_zh"]),
            name_en=str(item["name_en"]) if item.get("name_en") else None,
            node_type=str(item["node_type"]),
            sort_order=int(item.get("sort_order", 0)),
            series_codes=tuple(str(code) for code in item.get("series_codes", [])),
            icon_key=str(item["icon_key"]) if item.get("icon_key") else None,
        )
        for item in node_items
    )
    by_code = {node.code: node for node in nodes}
    if len(by_code) != len(nodes):
        raise RuntimeError("Taxonomy node codes must be unique")
    roots = [node for node in nodes if node.parent_code is None]
    if len(roots) != 1 or roots[0].code != "root":
        raise RuntimeError("Taxonomy must have exactly one root node named root")

    owners: dict[str, str] = {}
    for node in nodes:
        if node.parent_code is not None and node.parent_code not in by_code:
            raise RuntimeError(f"Unknown parent {node.parent_code} for node {node.code}")
        seen: set[str] = set()
        current = node
        while current.parent_code is not None:
            if current.code in seen:
                raise RuntimeError(f"Cycle detected at taxonomy node {current.code}")
            seen.add(current.code)
            if len(seen) > 64:
                raise RuntimeError("Taxonomy depth exceeds 64")
            current = by_code[current.parent_code]
        for canonical_code in node.series_codes:
            if canonical_code in owners:
                raise RuntimeError(
                    f"Series {canonical_code} belongs to both "
                    f"{owners[canonical_code]} and {node.code}"
                )
            owners[canonical_code] = node.code
    if set(owners) != set(source_codes):
        raise RuntimeError("Source and taxonomy registries must cover the same canonical codes")

    registry = CatalogRegistry(
        tree_code=str(taxonomy_payload["tree_code"]),
        expected_series_count=expected,
        indicators=indicators,
        nodes=nodes,
    )
    if registry.max_depth > 64:
        raise RuntimeError("Taxonomy depth exceeds 64")
    return registry


@lru_cache(maxsize=1)
def get_catalog_registry() -> CatalogRegistry:
    return load_catalog_registry(_repo_root())
