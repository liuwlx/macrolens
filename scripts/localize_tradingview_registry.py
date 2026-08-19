from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from macrolens_worker.providers.tradingview_names import tradingview_name_zh


def main() -> int:
    parser = argparse.ArgumentParser(description="Localize TradingView registry display names")
    parser.add_argument(
        "--input",
        type=Path,
        default=ROOT / "database" / "seed" / "tradingview_registry.json",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or args.input
    payload: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    indicators = payload.get("indicators")
    if not isinstance(indicators, list):
        raise TypeError("TradingView registry does not contain indicators")

    for item in indicators:
        canonical_code = str(item["canonical_code"])
        name_en = str(item["name_en"])
        item["name_zh"] = tradingview_name_zh(
            canonical_code,
            name_en,
            str(item.get("name_zh") or "") or None,
        )

    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Localized {len(indicators)} TradingView indicators in {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
