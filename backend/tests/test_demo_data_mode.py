from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from macrolens_api.config import Settings

ROOT = Path(__file__).resolve().parents[2]


def test_production_rejects_demo_data_mode() -> None:
    with pytest.raises(ValidationError, match="MACROLENS_DATA_MODE=demo"):
        Settings(
            environment="production",
            data_mode="demo",
            cookie_secure=True,
            web_origin="https://macrolens.example.com",
            jwt_secret="a" * 32,
            bootstrap_admin_password="a-secure-bootstrap-password",
            database_url="postgresql+asyncpg://app:secret@db/macrolens",
            database_url_sync="postgresql+psycopg://app:secret@db/macrolens",
        )


def test_demo_taxonomy_registry_owns_all_61_series_once_and_is_deep() -> None:
    from macrolens_api.demo_data import get_demo_registry

    registry = get_demo_registry()
    owners: dict[str, list[str]] = {}
    for node in registry.nodes:
        for canonical_code in node.series_codes:
            owners.setdefault(canonical_code, []).append(node.code)

    assert len(registry.series) == 61
    assert len(owners) == 61
    assert all(len(node_codes) == 1 for node_codes in owners.values())
    assert set(owners) == {series.canonical_code for series in registry.series}
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
    assert len(registry.leaf_series_codes("employment")) == 7


def test_demo_taxonomy_registry_preserves_utf8_chinese_names() -> None:
    registry_path = ROOT / "database" / "seed" / "taxonomy_registry.json"
    raw = registry_path.read_text(encoding="utf-8")
    assert "\ufffd" not in raw
    payload = json.loads(raw)
    names = {node["code"]: node["name_zh"] for node in payload["nodes"]}
    assert names["root"] == "美国宏观"
    assert names["pce-medical"] == "医疗服务"


def test_demo_http_reads_are_deterministic_without_a_database_and_mutations_fail_closed() -> None:
    probe = r"""
import asyncio
import json
import httpx

from macrolens_api.main import app
from macrolens_api import db


class ExplodingSessionFactory:
    def __call__(self, **kwargs):
        raise AssertionError("demo read attempted to construct a database session")


db.SessionLocal = ExplodingSessionFactory()


async def main():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        taxonomy = await client.get("/api/v1/taxonomies/macro-default")
        assert taxonomy.status_code == 200, taxonomy.text
        taxonomy_body = taxonomy.json()
        assert taxonomy_body["data_mode"] == "demo"

        browser = await client.get("/api/v1/series/browser")
        assert browser.status_code == 200, browser.text
        browser_body = browser.json()
        assert browser_body["data_mode"] == "demo"
        assert browser_body["data_as_of"] == "2026-08-01T00:00:00Z"
        assert browser_body["pagination"]["total"] == 61
        assert {item["availability"] for item in browser_body["items"]} == {"available"}

        repeated = await client.get("/api/v1/series/browser")
        assert repeated.json() == browser_body

        series_id = browser_body["items"][0]["series"]["id"]
        detail = await client.get(f"/api/v1/series/{series_id}")
        observations = await client.get(f"/api/v1/series/{series_id}/observations")
        revisions = await client.get(f"/api/v1/series/{series_id}/revisions")
        analytics = await client.get(f"/api/v1/series/{series_id}/analytics")
        capability = await client.get("/api/v1/ai/capabilities", params={"series_id": series_id})
        for response in (detail, observations, revisions, analytics, capability):
            assert response.status_code == 200, response.text
        assert observations.json()["meta"]["data_mode"] == "demo"
        assert observations.json()["data"]
        assert revisions.json()["items"]
        assert analytics.json()["data_mode"] == "demo"
        assert analytics.json()["statistics"]["count"] > 0
        assert capability.json() == {
            "series_id": series_id,
            "configured": False,
            "allowed": False,
            "reason_code": "demo_read_only",
            "reason": "Demo data mode is read-only.",
        }

        export = await client.get(f"/api/v1/series/{series_id}/export")
        assert export.status_code == 200, export.text
        assert export.headers["x-macrolens-data-mode"] == "demo"
        assert ".demo.csv" in export.headers["content-disposition"]
        header = export.content.decode("utf-8-sig").splitlines()[0].split(",")
        assert "data_mode" in header

        mutation = await client.post("/api/v1/ai/runs", json={})
        assert mutation.status_code == 409
        assert mutation.json()["code"] == "demo_read_only"


asyncio.run(main())
"""
    env = os.environ.copy()
    env.update(
        {
            "MACROLENS_DATA_MODE": "demo",
            "DATABASE_URL": "postgresql+asyncpg://demo:demo@127.0.0.1:1/unreachable",
            "DATABASE_URL_SYNC": "postgresql+psycopg://demo:demo@127.0.0.1:1/unreachable",
            "PYTHONPATH": str(ROOT / "backend" / "src"),
            "ENVIRONMENT": "test",
        }
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, json.dumps(
        {"stdout": result.stdout, "stderr": result.stderr}, ensure_ascii=False
    )
