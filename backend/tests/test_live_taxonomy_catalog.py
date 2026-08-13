from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from macrolens_api.routers import taxonomies
from macrolens_api.services.data_browser import BrowserCandidate, SourceBinding


class ScalarRows:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class FakeSession:
    def __init__(self, nodes: list[object]) -> None:
        self.nodes = nodes

    async def scalars(self, _statement: object) -> ScalarRows:
        return ScalarRows(self.nodes)


def _node(
    code: str,
    name_zh: str,
    *,
    parent_id: UUID | None,
    sort_order: int,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        code=code,
        name_zh=name_zh,
        name_en=name_zh,
        parent_id=parent_id,
        sort_order=sort_order,
        node_type="category",
        icon_key=None,
    )


def _candidate(node_id: UUID) -> BrowserCandidate:
    series_id = uuid4()
    series = SimpleNamespace(
        id=series_id,
        canonical_code="US.PCE.HEADLINE",
        name_zh="总PCE价格指数",
        name_en="Headline PCE price index",
        theme="inflation",
        frequency="monthly",
        unit_code="index",
        unit_label_zh="指数",
        default_transform="level",
        decimal_places=2,
        seasonal_adjustment="sa",
    )
    source = SimpleNamespace(
        id=7,
        series_id=series_id,
        provider_series_id="PCEPI",
        source_locator={},
        mapping_status="verified",
        is_primary=True,
    )
    dataset = SimpleNamespace(id=8, code="PCE", provider_id=9)
    provider = SimpleNamespace(
        id=9,
        code="BEA_API",
        name="BEA",
        attribution_text="BEA",
        license_class="public",
        redistribution_ok=True,
    )
    candidate = BrowserCandidate(series=series)  # type: ignore[arg-type]
    binding = SourceBinding(source, dataset, provider)  # type: ignore[arg-type]
    candidate.sources[source.id] = binding
    candidate.catalog_sources[source.id] = binding
    candidate.node_ids.add(node_id)
    return candidate


async def test_live_taxonomy_search_preserves_each_ancestor_and_direct_children(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = _node("root", "宏观经济", parent_id=None, sort_order=0)
    inflation = _node("inflation", "通胀", parent_id=root.id, sort_order=1)
    pce = _node("pce", "PCE", parent_id=inflation.id, sort_order=1)
    headline = _node("pce-headline", "总PCE", parent_id=pce.id, sort_order=1)
    nodes = [root, inflation, pce, headline]
    candidate = _candidate(headline.id)

    async def candidates(_session: object) -> list[BrowserCandidate]:
        return [candidate]

    monkeypatch.setattr(taxonomies, "settings", SimpleNamespace(data_mode="live"))
    monkeypatch.setattr(taxonomies, "_load_candidates", candidates)
    node_codes_by_id = {node.id: node.code for node in nodes}
    monkeypatch.setattr(
        taxonomies,
        "get_catalog_registry",
        lambda: SimpleNamespace(
            tree_code="macro-default",
            nodes=[
                SimpleNamespace(
                    code=node.code,
                    parent_code=node_codes_by_id.get(node.parent_id),
                )
                for node in nodes
            ],
            indicators=[SimpleNamespace(canonical_code=candidate.series.canonical_code)],
        ),
    )
    session = FakeSession(nodes)

    for parent_id, expected in [
        (None, root),
        (root.id, inflation),
        (inflation.id, pce),
        (pce.id, headline),
    ]:
        response = await taxonomies.taxonomy_children(
            session,  # type: ignore[arg-type]
            tree_code="macro-default",
            parent_id=parent_id,
            q="headline",
            scope="all",
            provider="BEA_API",
            theme="inflation",
            frequency="monthly",
            unit="index",
            seasonal_adjustment="sa",
        )
        assert [node.id for node in response.nodes] == [expected.id]
        assert response.nodes[0].descendant_series_count == 1

    leaf = await taxonomies.taxonomy_children(
        session,  # type: ignore[arg-type]
        tree_code="macro-default",
        parent_id=headline.id,
        q="headline",
        scope="all",
        provider="BEA_API",
        theme="inflation",
        frequency="monthly",
        unit="index",
        seasonal_adjustment="sa",
    )
    assert leaf.nodes == []
    assert [series.canonical_code for series in leaf.series] == ["US.PCE.HEADLINE"]
