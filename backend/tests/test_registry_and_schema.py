import json
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from macrolens_api.cli import _theme, obsolete_tradingview_node_codes
from macrolens_api.main import app
from macrolens_api.models import Base, ObservationVintage, PublicationBatch, SavedView

ROOT = Path(__file__).resolve().parents[2]


def test_source_registry_is_complete_and_unique() -> None:
    payload = json.loads((ROOT / "database/seed/source_registry.json").read_text(encoding="utf-8"))
    indicators = payload["indicators"]
    assert len(indicators) >= 61
    codes = [item["canonical_code"] for item in indicators]
    assert len(codes) == len(set(codes))
    assert all(item.get("recommended_source") for item in indicators)
    assert all(item.get("mapping_status") for item in indicators)


def test_tradingview_registry_contains_v1_symbols() -> None:
    payload = json.loads(
        (ROOT / "database/seed/tradingview_registry.json").read_text(encoding="utf-8")
    )
    indicators = payload["indicators"]
    assert len(indicators) == 535
    assert len({item["canonical_code"] for item in indicators}) == 535
    assert len({item["provider_series_id"] for item in indicators}) == 535
    assert all(item["provider_series_id"].startswith("ECONOMICS:US") for item in indicators)
    assert sum(item["mapping_status"] == "READY" for item in indicators) == 340
    unavailable = [item for item in indicators if item["mapping_status"] == "UNAVAILABLE_US"]
    assert len(unavailable) == 195
    assert all(
        item.get("availability_evidence") == {"code": "no_such_symbol", "geography": "US"}
        for item in unavailable
    )
    domains = {
        "rates-policy",
        "inflation",
        "growth",
        "employment",
        "credit-banking",
        "financial-markets",
        "housing-household",
    }
    nodes = payload["nodes"]
    base_taxonomy = json.loads(
        (ROOT / "database/seed/taxonomy_registry.json").read_text(encoding="utf-8")
    )
    base_node_codes = {node["code"] for node in base_taxonomy["nodes"]}
    owners = {
        canonical_code: node["code"] for node in nodes for canonical_code in node["series_codes"]
    }
    assert {node["parent_code"] for node in nodes} == domains
    assert all(node["code"].startswith("tv-fed-") for node in nodes)
    assert {node["code"] for node in nodes}.issubset(base_node_codes)
    assert "tv-root" not in {node["code"] for node in nodes}
    assert len(owners) == 535
    assert set(owners) == {item["canonical_code"] for item in indicators}
    assert all(owners[item["canonical_code"]] == item["primary_topic"] for item in indicators)
    assert all(isinstance(item["cross_tags"], list) for item in indicators)
    topic_domains = {node["code"]: node["parent_code"] for node in nodes}
    assert all(
        len(item["cross_tags"]) == len(set(item["cross_tags"]))
        and set(item["cross_tags"]).issubset(domains)
        and topic_domains[item["primary_topic"]] not in item["cross_tags"]
        for item in indicators
    )
    assert {item["theme"] for item in indicators} == {
        "货币政策与利率",
        "通胀与通胀预期",
        "实体经济与增长",
        "劳动力市场",
        "信贷与银行体系",
        "金融条件与金融市场",
        "住房与家庭部门",
    }


def test_tradingview_seed_retires_only_obsolete_extension_nodes() -> None:
    payload = json.loads(
        (ROOT / "database/seed/tradingview_registry.json").read_text(encoding="utf-8")
    )
    desired = {node["code"] for node in payload["nodes"]}
    legacy = {
        "tv-root",
        "tv-growth",
        "tv-labor",
        "tv-inflation",
        "tv-health",
        "tv-policy",
        "tv-trade",
        "tv-government",
        "tv-business",
        "tv-consumer",
        "tv-housing",
        "tv-taxes",
        "tv-energy",
        "tv-climate",
    }

    assert obsolete_tradingview_node_codes(desired | legacy, desired) == legacy


@pytest.mark.parametrize(
    ("canonical_code", "theme"),
    [
        ("US.FED.FUNDS", "货币政策与利率"),
        ("US.CPI.HEADLINE", "通胀与通胀预期"),
        ("US.REAL.GDP", "实体经济与增长"),
        ("US.PAYROLLS", "劳动力市场"),
        ("US.BANK.CREDIT", "信贷与银行体系"),
        ("US.FINANCIAL.CONDITIONS", "金融条件与金融市场"),
        ("US.MORTGAGE.30Y", "住房与家庭部门"),
    ],
)
def test_official_series_theme_uses_the_same_seven_research_domains(
    canonical_code: str,
    theme: str,
) -> None:
    assert _theme(canonical_code) == theme


def test_all_tables_compile_for_postgresql() -> None:
    dialect = postgresql.dialect()
    assert len(Base.metadata.tables) >= 40
    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=dialect))
        assert "CREATE TABLE" in sql


def test_observation_vintage_has_append_only_identity() -> None:
    columns = ObservationVintage.__table__.columns
    assert {"source_series_id", "period_start", "vintage_at"}.issubset(columns.keys())
    assert columns["value"].nullable


def test_saved_views_and_publication_batches_are_persistent() -> None:
    assert {"workspace_id", "owner_user_id", "definition"}.issubset(
        SavedView.__table__.columns.keys()
    )
    assert {"provider_id", "run_id", "status", "previous_batch_id"}.issubset(
        PublicationBatch.__table__.columns.keys()
    )


def test_api_route_surface() -> None:
    paths = set(app.openapi()["paths"])
    expected = {
        "/api/v1/health",
        "/api/v1/series",
        "/api/v1/compare/query",
        "/api/v1/release-events",
        "/api/v1/fomc/meetings",
        "/api/v1/documents",
        "/api/v1/ai/runs",
        "/api/v1/me/projects",
        "/api/v1/me/alerts",
        "/api/v1/me/reports",
        "/api/v1/me/projects/{project_id}/shares",
        "/api/v1/shared/projects/{token}",
        "/api/v1/release-events/{event_id}/forecasts",
        "/api/v1/release-events/{event_id}/market-reactions",
        "/api/v1/me/saved-views",
        "/api/v1/me/notes",
        "/api/v1/admin/documents/fetch",
        "/api/v1/admin/publication-batches/{batch_id}/rollback",
        "/api/v1/admin/providers/{provider_code}/sync",
        "/api/v1/admin/providers/{provider_code}/series/{series_id}/history",
        "/api/v1/admin/jobs/{job_id}",
    }
    assert expected.issubset(paths)


def test_verified_provider_registry_pins_known_history_boundaries_and_routes() -> None:
    payload = json.loads((ROOT / "database/seed/source_registry.json").read_text(encoding="utf-8"))
    by_code = {item["canonical_code"]: item for item in payload["indicators"]}
    assert by_code["US.AVERAGE.HOURLY"]["locator"]["expected_first_period"] == "2006-03-01"
    assert by_code["US.ECI"]["locator"]["expected_first_period"] == "2001-01-01"
    assert by_code["US.JOB.OPENINGS"]["locator"]["expected_first_period"] == "2000-12-01"
    assert by_code["US.FED.FUNDS"]["locator"]["expected_first_period"] == "2000-07-03"
    assert by_code["US.BREAKEVEN.5Y5Y"]["locator"]["expected_first_period"] == "2003-01-02"
    assert by_code["US.INDUSTRIAL.PRODUCTION"]["locator"]["expected_first_period"] == "1919-01-01"
    assert by_code["US.FED.ASSETS"]["locator"]["expected_first_period"] == "2002-12-18"
    assert by_code["US.FED.ASSETS"]["recommended_source"] == "FED_BOARD_FILES"
    assert by_code["US.FED.ASSETS"]["provider_series_id"] == "RESPPA_N.WW"
    assert by_code["US.BANK.RESERVES"]["locator"]["expected_first_period"] == "2002-12-18"
    assert by_code["US.FED.MBS"]["locator"]["expected_first_period"] == "2002-12-18"
    assert by_code["US.FED.MBS"]["recommended_source"] == "FED_BOARD_FILES"
    assert by_code["US.FED.MBS"]["provider_series_id"] == "RESPPALGASMO_N.WW"
    assert by_code["US.DOLLAR.INDEX"]["locator"]["expected_first_period"] == "2006-01-02"
    assert by_code["US.FINANCIAL.CONDITIONS"]["locator"]["expected_first_period"] == "1971-01-08"
    assert by_code["US.BANK.CREDIT"]["provider_series_id"] == "B1001NCBA"
    assert by_code["US.BANK.CREDIT"]["locator"]["expected_first_period"] == "1973-01-03"
    assert by_code["US.CONSUMER.CREDIT"]["locator"]["expected_first_period"] == "1943-01-01"
    assert by_code["US.CARD.DELINQUENCY"]["locator"]["expected_first_period"] == "1991-01-01"
    assert by_code["US.CARD.DELINQUENCY"]["recommended_source"] == "FED_BOARD_FILES"
    assert by_code["US.CARD.DELINQUENCY"]["provider_series_id"] == "STFBQDCC%STFBAILCC_XEOP_MA.Q"
    assert by_code["US.WTI"]["locator"]["expected_first_period"] == "1986-01-02"
    assert by_code["US.SLOOS"]["locator"]["expected_first_period"] == "1990-04-01"
    assert by_code["US.SLOOS"]["recommended_source"] == "FED_BOARD_FILES"
    assert by_code["US.SLOOS"]["provider_series_id"] == "SUBLPDCILS_N.Q"
    claims = by_code["US.INITIAL.CLAIMS"]
    assert claims["recommended_source"] == "FRED_API"
    assert claims["provider_series_id"] == "ICSA"
    assert claims["locator"]["scale_factor"] == "0.001"
    rrp = by_code["US.REVERSE.REPO"]["locator"]
    assert rrp["route"] == "rp/results/search.json"
    assert rrp["field"] == "totalAmtAccepted"
    assert rrp["params"] == {
        "operationTypes": "reverserepo",
        "securityType": "tsy",
        "term": "Overnight",
    }


def test_bea_registry_pins_live_audited_identities_and_explicit_blockers() -> None:
    payload = json.loads((ROOT / "database/seed/source_registry.json").read_text(encoding="utf-8"))
    bea = [item for item in payload["indicators"] if item["recommended_source"] == "BEA_API"]
    ready = [item for item in bea if item["mapping_status"] == "READY"]
    blocked = {item["canonical_code"] for item in bea if item["mapping_status"] != "READY"}

    assert len(ready) == 22
    assert blocked == {"US.PCE.NONHOUSING", "US.PCE.LONGTERM.CARE"}
    for item in ready:
        locator = item["locator"]
        assert locator["series_code"]
        if item["provider_series_id"] is not None:
            assert locator["series_code"] == item["provider_series_id"]
        assert locator["line_number"]
        assert locator["line_description"]
        assert locator["metric_name"]
        assert locator["cl_unit"]
        assert locator["unit_mult"]
        assert locator["expected_first_period"]

    personal = next(item for item in ready if item["canonical_code"] == "US.PERSONAL.CONSUMPTION")
    assert personal["locator"]["table_name"] == "T10106"
    assert personal["locator"]["frequency"] == "Q"
    assert personal["locator"]["line_number"] == "2"

    durable = next(
        item for item in payload["indicators"] if item["canonical_code"] == "US.DURABLE.ORDERS"
    )
    assert durable["mapping_status"] == "READY"
    assert durable["provider_series_id"] == "MDM"
    assert durable["locator"]["dimensions"] == {
        "data_type_code": "NO",
        "time_slot_id": "0",
        "seasonally_adj": "yes",
        "program_code": "M3ADV",
        "category_code": "MDM",
        "geo_level_code": "US",
        "error_data": "no",
        "for": "us:*",
    }


def test_seed_command_updates_existing_source_mappings() -> None:
    seed_source = (ROOT / "backend/src/macrolens_api/cli.py").read_text(encoding="utf-8")
    assert 'source_series.source_locator = item.get("locator") or {}' in seed_source
    assert 'source_series.provider_series_id = item.get("provider_series_id")' in seed_source
    assert "source_series.mapping_status = status" in seed_source
