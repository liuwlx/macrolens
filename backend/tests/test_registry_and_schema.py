import json
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

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
    assert by_code["US.BANK.RESERVES"]["locator"]["expected_first_period"] == "2002-12-18"
    assert by_code["US.FED.MBS"]["locator"]["expected_first_period"] == "2002-12-18"
    assert by_code["US.DOLLAR.INDEX"]["locator"]["expected_first_period"] == "2006-01-02"
    assert by_code["US.FINANCIAL.CONDITIONS"]["locator"]["expected_first_period"] == "1971-01-08"
    assert by_code["US.BANK.CREDIT"]["provider_series_id"] == "TOTBKCR"
    assert by_code["US.BANK.CREDIT"]["locator"]["expected_first_period"] == "1973-01-03"
    assert by_code["US.CONSUMER.CREDIT"]["locator"]["expected_first_period"] == "1943-01-01"
    assert by_code["US.CARD.DELINQUENCY"]["locator"]["expected_first_period"] == "1991-01-01"
    assert by_code["US.WTI"]["locator"]["expected_first_period"] == "1986-01-02"
    assert by_code["US.SLOOS"]["locator"]["expected_first_period"] == "1990-04-01"
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


def test_seed_command_updates_existing_source_mappings() -> None:
    seed_source = (ROOT / "backend/src/macrolens_api/cli.py").read_text(encoding="utf-8")
    assert 'source_series.source_locator = item.get("locator") or {}' in seed_source
    assert 'source_series.provider_series_id = item.get("provider_series_id")' in seed_source
    assert "source_series.mapping_status = status" in seed_source
