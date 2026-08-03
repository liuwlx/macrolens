#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET", "openapi-generation-secret-at-least-thirty-two-characters")

from macrolens_api.main import app  # noqa: E402


def normalized(value: object) -> str:
    return yaml.safe_dump(value, allow_unicode=True, sort_keys=False, width=120)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the checked-in contract differs.")
    parser.add_argument("--json", action="store_true", help="Also write OpenAPI JSON.")
    args = parser.parse_args()

    schema = app.openapi()
    rendered = normalized(schema)
    target = ROOT / "macrolens_openapi.yaml"
    if args.check:
        if not target.exists() or normalized(yaml.safe_load(target.read_text())) != rendered:
            print("macrolens_openapi.yaml is out of date", file=sys.stderr)
            return 1
        print(f"OpenAPI is current: {len(schema.get('paths', {}))} paths")
        return 0

    target.write_text(rendered, encoding="utf-8")
    if args.json:
        (ROOT / "macrolens_openapi.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(f"Wrote {target} with {len(schema.get('paths', {}))} paths")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
