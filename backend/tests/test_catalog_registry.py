from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from macrolens_api.catalog_registry import get_catalog_registry
from macrolens_api.errors import AppError
from macrolens_api.services.data_browser import _load_candidates


def test_catalog_registry_reconciles_all_61_series_with_deep_taxonomy() -> None:
    registry = get_catalog_registry()

    assert registry.expected_series_count == 61
    assert len(registry.indicators) == 61
    assert len(registry.owner_by_series_code) == 61
    assert set(registry.owner_by_series_code) == {
        indicator.canonical_code for indicator in registry.indicators
    }
    assert registry.max_depth >= 5
    assert registry.path_for("US.PCE.HOSPITAL") == (
        "root",
        "inflation",
        "pce",
        "pce-core",
        "pce-core-services",
        "pce-core-services-nonhousing",
        "pce-medical",
        "pce-medical-hospital",
    )


def test_catalog_registry_exposes_exact_direct_and_descendant_membership() -> None:
    registry = get_catalog_registry()

    assert registry.nodes_by_code["pce-medical"].series_codes == ("US.PCE.MEDICAL",)
    assert set(registry.descendant_series_codes("pce-medical")) == {
        "US.PCE.MEDICAL",
        "US.PCE.HOSPITAL",
        "US.PCE.PHYSICIAN",
        "US.PCE.OTHER.PROFESSIONAL",
        "US.PCE.DENTAL",
        "US.PCE.MEDICAL.EQUIPMENT",
        "US.PCE.PRESCRIPTION",
        "US.PCE.HEALTH.INSURANCE",
        "US.PCE.LONGTERM.CARE",
    }


class ResultRows:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows

    def all(self) -> list[object]:
        return self.rows


class FakeSession:
    def __init__(self, rows: list[object]) -> None:
        self.rows = rows
        self.calls = 0

    async def execute(self, _statement: object) -> ResultRows:
        self.calls += 1
        return ResultRows(self.rows if self.calls == 1 else [])


def _catalog_rows(limit: int = 61) -> list[object]:
    registry = get_catalog_registry()
    rows: list[object] = []
    for index, indicator in enumerate(registry.indicators[:limit], start=1):
        item = indicator.payload
        series_id = uuid4()
        series = SimpleNamespace(
            id=series_id,
            canonical_code=indicator.canonical_code,
            status="draft",
        )
        source = SimpleNamespace(
            id=index,
            is_primary=False,
            mapping_status="needs_review",
        )
        provider = SimpleNamespace(id=index, code=item["recommended_source"])
        dataset = SimpleNamespace(id=index, provider_id=index)
        taxonomy_node = SimpleNamespace(
            id=uuid4(),
            code=registry.owner_by_series_code[indicator.canonical_code].code,
        )
        taxonomy = SimpleNamespace(
            node_id=taxonomy_node.id,
            display_order=index,
        )
        rows.append((series, source, dataset, provider, taxonomy, taxonomy_node))
    return rows


async def test_live_catalog_loader_keeps_all_61_unverified_draft_entries() -> None:
    candidates = await _load_candidates(FakeSession(_catalog_rows()))  # type: ignore[arg-type]

    assert len(candidates) == 61
    assert {candidate.series.canonical_code for candidate in candidates} == {
        indicator.canonical_code for indicator in get_catalog_registry().indicators
    }
    assert all(not candidate.sources for candidate in candidates)
    assert all(len(candidate.catalog_sources) == 1 for candidate in candidates)


async def test_live_catalog_loader_fails_closed_on_partial_registry_projection() -> None:
    with pytest.raises(AppError) as captured:
        await _load_candidates(FakeSession(_catalog_rows(limit=60)))  # type: ignore[arg-type]

    assert captured.value.status_code == 503
    assert captured.value.code == "catalog_registry_mismatch"


async def test_live_catalog_loader_fails_closed_on_taxonomy_ownership_drift() -> None:
    rows = _catalog_rows()
    rows[0][-1].code = "wrong-owner"  # type: ignore[index,union-attr]

    with pytest.raises(AppError) as captured:
        await _load_candidates(FakeSession(rows))  # type: ignore[arg-type]

    assert captured.value.status_code == 503
    assert captured.value.extra["ownership_mismatch_count"] == 1
