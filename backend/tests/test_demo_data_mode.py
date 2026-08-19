from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

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
    assert registry.max_depth == 2
    assert registry.path_for("US.PCE.HOSPITAL") == (
        "root",
        "inflation",
        "tv-fed-inflation-pce",
    )
    assert len(registry.leaf_series_codes("employment")) == 7


def test_demo_taxonomy_registry_preserves_utf8_chinese_names() -> None:
    registry_path = ROOT / "database" / "seed" / "taxonomy_registry.json"
    raw = registry_path.read_text(encoding="utf-8")
    assert "\ufffd" not in raw
    payload = json.loads(raw)
    names = {node["code"]: node["name_zh"] for node in payload["nodes"]}
    assert names["root"] == "美国宏观与金融体系"
    assert names["tv-fed-inflation-pce"] == "PCE 通胀"


def test_demo_catalog_reads_skip_data_session_but_browser_uses_real_auth_session() -> None:
    probe = r"""
import asyncio
import httpx

from macrolens_api import db
from macrolens_api.demo_data import get_demo_registry
from macrolens_api.main import app


class ExplodingSessionFactory:
    def __call__(self, **kwargs):
        raise AssertionError("demo catalog read attempted to construct a database session")


async def main():
    db.SessionLocal = ExplodingSessionFactory()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        taxonomy = await client.get("/api/v1/taxonomies/macro-default")
        assert taxonomy.status_code == 200, taxonomy.text
        series_id = get_demo_registry().series[0].id
        detail = await client.get(f"/api/v1/series/{series_id}")
        assert detail.status_code == 200, detail.text

        auth_session_calls = 0

        async def fake_auth_session():
            nonlocal auth_session_calls
            auth_session_calls += 1
            yield object()

        app.dependency_overrides[db.get_session] = fake_auth_session
        try:
            browser = await client.get("/api/v1/series/browser")
        finally:
            app.dependency_overrides.clear()
        assert browser.status_code == 401, browser.text
        assert browser.json()["code"] == "authentication_required"
        assert auth_session_calls == 1


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


def test_demo_missing_workspace_returns_read_only_conflict_without_database_write() -> None:
    probe = r"""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import httpx

from macrolens_api import db
from macrolens_api.dependencies import get_current_user
from macrolens_api.main import app


class WorkspaceSessionSpy:
    def __init__(self):
        self.add_calls = 0
        self.commit_calls = 0
        self.refresh_calls = 0

    async def scalar(self, statement):
        return None

    def add(self, workspace):
        self.add_calls += 1

    async def commit(self):
        self.commit_calls += 1

    async def refresh(self, workspace):
        self.refresh_calls += 1


async def authenticated_user():
    return SimpleNamespace(id=uuid4(), display_name="Demo Researcher")


async def main():
    session = WorkspaceSessionSpy()

    async def workspace_session():
        yield session

    app.dependency_overrides[get_current_user] = authenticated_user
    app.dependency_overrides[db.get_session] = workspace_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/api/v1/series/browser")
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "demo_read_only"
        assert session.add_calls == 0
        assert session.commit_calls == 0
        assert session.refresh_calls == 0
    finally:
        app.dependency_overrides.clear()


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


@pytest.mark.asyncio
async def test_live_missing_workspace_still_creates_and_commits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from macrolens_api import dependencies

    class WorkspaceSessionSpy:
        def __init__(self) -> None:
            self.added: list[object] = []
            self.commit_calls = 0
            self.refresh_calls = 0

        async def scalar(self, statement: object) -> None:
            return None

        def add(self, workspace: object) -> None:
            self.added.append(workspace)

        async def commit(self) -> None:
            self.commit_calls += 1

        async def refresh(self, workspace: object) -> None:
            self.refresh_calls += 1

    if hasattr(dependencies, "settings"):
        monkeypatch.setattr(dependencies.settings, "data_mode", "live")
    session = WorkspaceSessionSpy()
    user = SimpleNamespace(id=uuid4(), display_name="Live Researcher")

    workspace = await dependencies.get_current_workspace(session, user)  # type: ignore[arg-type]

    assert workspace.owner_user_id == user.id
    assert len(session.added) == 1
    assert session.commit_calls == 1
    assert session.refresh_calls == 1


def test_demo_taxonomy_search_and_filters_keep_only_matching_direct_child_branches() -> None:
    probe = r"""
import asyncio
import httpx

from macrolens_api.demo_data import DEMO_PROVIDER, get_demo_registry
from macrolens_api.main import app


async def main():
    registry = get_demo_registry()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        parent_id = None
        expected_path = (
            "root",
            "inflation",
            "tv-fed-inflation-pce",
        )
        for expected_code in expected_path:
            params = {"scope": "all", "q": "医院服务"}
            if parent_id is not None:
                params["parent_id"] = parent_id
            response = await client.get(
                "/api/v1/taxonomies/macro-default/children", params=params
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert [node["code"] for node in body["nodes"]] == [expected_code]
            node = body["nodes"][0]
            assert node["direct_series_count"] == (
                1 if expected_code == "tv-fed-inflation-pce" else 0
            )
            assert node["descendant_series_count"] == 1
            assert body["series"] == []
            parent_id = node["id"]

        terminal = await client.get(
            "/api/v1/taxonomies/macro-default/children",
            params={"parent_id": parent_id, "scope": "all", "q": "医院服务"},
        )
        assert terminal.status_code == 200, terminal.text
        assert terminal.json()["nodes"] == []
        assert [item["canonical_code"] for item in terminal.json()["series"]] == [
            "US.PCE.HOSPITAL"
        ]

        target = registry.series_by_code["US.INITIAL.CLAIMS"]
        employment = registry.nodes_by_code["employment"]
        filters = {
            "parent_id": str(employment.id),
            "scope": "all",
            "provider": DEMO_PROVIDER.code,
            "theme": target.theme,
            "frequency": target.frequency,
            "unit": target.unit_code,
            "seasonal_adjustment": target.seasonal_adjustment,
        }
        filtered = await client.get(
            "/api/v1/taxonomies/macro-default/children", params=filters
        )
        assert filtered.status_code == 200, filtered.text
        filtered_body = filtered.json()
        assert [node["code"] for node in filtered_body["nodes"]] == [
            "tv-fed-labor-separations"
        ]
        assert filtered_body["nodes"][0]["direct_series_count"] == 1
        assert filtered_body["nodes"][0]["descendant_series_count"] == 1

        filters["parent_id"] = filtered_body["nodes"][0]["id"]
        terminal_filtered = await client.get(
            "/api/v1/taxonomies/macro-default/children", params=filters
        )
        assert terminal_filtered.status_code == 200, terminal_filtered.text
        assert terminal_filtered.json()["nodes"] == []
        assert [item["canonical_code"] for item in terminal_filtered.json()["series"]] == [
            "US.INITIAL.CLAIMS"
        ]


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


def test_demo_observation_windows_have_exact_frequency_counts_from_fixed_as_of() -> None:
    probe = r"""
import asyncio
from datetime import datetime

import httpx

from macrolens_api.demo_data import get_demo_registry
from macrolens_api.dependencies import get_current_user, get_current_workspace
from macrolens_api.main import app


async def authenticated_principal():
    return object()


async def main():
    expected_counts = {"daily": 260, "weekly": 156, "monthly": 120, "quarterly": 40}
    registry = get_demo_registry()
    representatives = {
        frequency: next(item for item in registry.series if item.frequency == frequency)
        for frequency in expected_counts
    }
    app.dependency_overrides[get_current_user] = authenticated_principal
    app.dependency_overrides[get_current_workspace] = authenticated_principal
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            for frequency, expected_count in expected_counts.items():
                response = await client.get(
                    f"/api/v1/series/{representatives[frequency].id}/observations"
                )
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["meta"]["frequency"] == frequency
                assert len(body["data"]) == expected_count
                periods = [item["period_start"] for item in body["data"]]
                assert periods == sorted(periods)
                assert len(set(periods)) == expected_count
                published = [
                    datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
                    for item in body["data"]
                ]
                assert max(published).isoformat() <= "2026-08-01T00:00:00+00:00"
    finally:
        app.dependency_overrides.clear()


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


def test_demo_http_reads_are_deterministic_without_a_database_and_mutations_fail_closed() -> None:
    probe = r"""
import asyncio
import json
import httpx

from macrolens_api.main import app
from macrolens_api import db
from macrolens_api.dependencies import get_current_user, get_current_workspace


class ExplodingSessionFactory:
    def __call__(self, **kwargs):
        raise AssertionError("demo read attempted to construct a database session")


db.SessionLocal = ExplodingSessionFactory()


async def authenticated_principal():
    return object()


app.dependency_overrides[get_current_user] = authenticated_principal
app.dependency_overrides[get_current_workspace] = authenticated_principal


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
