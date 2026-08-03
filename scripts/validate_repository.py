#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "README.md",
    "AGENTS.md",
    ".env.example",
    "docker-compose.yml",
    "backend/Dockerfile",
    "backend/alembic/versions/0001_initial.py",
    "apps/web/Dockerfile",
    "apps/web/package.json",
    "database/seed/source_registry.json",
    "macrolens_openapi.yaml",
    ".github/workflows/ci.yml",
    "infrastructure/terraform/main.tf",
]


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    for name in REQUIRED:
        if not (ROOT / name).is_file():
            fail(f"missing required file: {name}")

    env_text = (ROOT / ".env.example").read_text()
    for secret in ["OPENAI_API_KEY", "JWT_SECRET", "POSTGRES_PASSWORD"]:
        if secret not in env_text:
            fail(f"missing environment contract: {secret}")

    registry = json.loads((ROOT / "database/seed/source_registry.json").read_text())
    entries = registry.get("series") or registry.get("indicators") or registry if isinstance(registry, dict) else registry
    if not isinstance(entries, list) or len(entries) < 50:
        fail("source registry must contain at least 50 series mappings")
    codes = [item.get("canonical_code") for item in entries]
    if None in codes or len(codes) != len(set(codes)):
        fail("canonical series codes must be present and unique")

    spec = yaml.safe_load((ROOT / "macrolens_openapi.yaml").read_text())
    paths = spec.get("paths", {})
    for path in [
        "/api/v1/series",
        "/api/v1/release-events",
        "/api/v1/documents",
        "/api/v1/fomc/meetings",
        "/api/v1/ai/runs",
        "/api/v1/me/projects",
        "/api/v1/me/saved-views",
        "/api/v1/me/reports",
        "/api/v1/admin/documents/fetch",
        "/api/v1/admin/publication-batches/{batch_id}/rollback",
    ]:
        if path not in paths:
            fail(f"OpenAPI route missing: {path}")

    forbidden = ["change-me-now\n", "sk-proj-", "BEGIN PRIVATE KEY"]
    for file in ROOT.rglob("*"):
        if not file.is_file() or any(part in {".git", ".venv", "node_modules"} for part in file.parts):
            continue
        try:
            text = file.read_text()
        except UnicodeDecodeError:
            continue
        for marker in forbidden:
            if marker in text and file.name not in {".env.example", "validate_repository.py"}:
                fail(f"possible secret/default credential in {file.relative_to(ROOT)}")

    print(f"Repository contract valid: {len(entries)} source series, {len(paths)} API paths")


if __name__ == "__main__":
    main()
