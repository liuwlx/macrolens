#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import importlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

TradingViewAdapter: Any = importlib.import_module(
    "macrolens_worker.providers.tradingview"
).TradingViewAdapter


CATEGORIES = {
    "gdp": ("tv-growth", "实体经济与增长", "GDP and Growth", 10),
    "lbr": ("tv-labor", "劳动力市场", "Labor Market", 20),
    "prce": ("tv-inflation", "通胀与价格", "Prices", 30),
    "hlth": ("tv-health", "健康", "Health", 40),
    "mny": ("tv-policy", "货币、利率与流动性", "Money and Rates", 50),
    "trd": ("tv-trade", "贸易与国际收支", "Trade", 60),
    "gov": ("tv-government", "财政与政府", "Government", 70),
    "bsnss": ("tv-business", "企业与景气", "Business", 80),
    "cnsm": ("tv-consumer", "消费者与家庭", "Consumer", 90),
    "hse": ("tv-housing", "住房与房地产", "Housing", 100),
    "txs": ("tv-taxes", "税收", "Taxes", 110),
    "enrg": ("tv-energy", "能源", "Energy", 120),
    "clmt": ("tv-climate", "气候", "Climate", 130),
}

FREQUENCIES = {
    "D": "日度",
    "W": "周度",
    "M": "月度",
    "3M": "季度",
    "12M": "年度",
}


def route_map(js_source: str) -> dict[str, str | None]:
    matches = re.finditer(
        r'\{ticker:"(?P<ticker>[^"]+)",name:.*?,route:(?:"(?P<route>[^"]*)"|null)',
        js_source,
    )
    return {
        match.group("ticker"): match.group("route") or None
        for match in matches
    }


def readable_name(ticker: str, route: str | None) -> str:
    if not route:
        return ticker
    value = route.replace("-(jobs-created)", " jobs created")
    value = value.replace("(", " ").replace(")", " ")
    return " ".join(value.replace("-", " ").split()).title()


def flag_value(flags: list[str], prefix: str, fallback: str) -> str:
    for flag in flags:
        if flag.startswith(prefix):
            return flag.removeprefix(prefix)
    return fallback


async def probe(
    categories: list[dict[str, Any]],
) -> dict[str, dict[str, str]]:
    valid: dict[str, dict[str, str]] = {}
    for category in categories:
        tickers = [str(item) for item in category["tickers"]]
        mappings = [
            (
                SimpleNamespace(
                    id=index,
                    provider_series_id=f"ECONOMICS:US{ticker}",
                    source_frequency="monthly",
                    source_unit=None,
                    source_locator={},
                ),
                SimpleNamespace(id=1, code="TRADINGVIEW_ECONOMICS"),
            )
            for index, ticker in enumerate(tickers, start=1)
        ]
        results = None
        for attempt in range(1, 4):
            try:
                results = await TradingViewAdapter(client=None).fetch(  # type: ignore[arg-type]
                    SimpleNamespace(code="TRADINGVIEW_WEB"),
                    mappings,
                    mode="latest",
                )
                break
            except (ConnectionError, OSError, TimeoutError) as exc:
                if attempt == 3:
                    raise RuntimeError(
                        f"TradingView probe failed for category {category['id']}"
                    ) from exc
                await asyncio.sleep(attempt)
        if results is None:
            raise RuntimeError(f"TradingView probe returned no result for {category['id']}")
        observations = [item for result in results for item in result.observations]
        for observation in observations:
            ticker = tickers[observation.source_series_id - 1]
            valid[ticker] = {
                "frequency_code": flag_value(
                    observation.quality_flags,
                    "tradingview_frequency:",
                    "M",
                ),
                "unit": flag_value(
                    observation.quality_flags,
                    "tradingview_unit:",
                    "VALUE",
                ),
            }
        print(
            f"{category['id']}: {len(observations)}/{len(tickers)} valid",
            file=sys.stderr,
            flush=True,
        )
        await asyncio.sleep(0.25)
    return valid


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis-root", type=Path, required=True)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "database" / "seed" / "tradingview_registry.json",
    )
    parser.add_argument("--skip-probe", action="store_true")
    args = parser.parse_args()

    catalog = json.loads(
        (args.analysis_root / "raw" / "economy-catalog.json").read_text(
            encoding="utf-8"
        )
    )
    js_path = next((args.analysis_root / "assets").glob("1263.*.js"))
    routes = route_map(js_path.read_text(encoding="utf-8"))
    categories = list(catalog["categories"])

    existing = (
        json.loads(args.output.read_text(encoding="utf-8"))
        if args.output.is_file()
        else {"indicators": []}
    )
    overrides = {
        str(item["provider_series_id"]).removeprefix("ECONOMICS:US"): item
        for item in existing.get("indicators", [])
    }

    memberships: dict[str, list[str]] = {}
    ordered_tickers: list[str] = []
    for category in categories:
        category_id = str(category["id"])
        for raw_ticker in category["tickers"]:
            ticker = str(raw_ticker)
            if ticker not in memberships:
                memberships[ticker] = []
                ordered_tickers.append(ticker)
            memberships[ticker].append(category_id)
    if len(ordered_tickers) != 535:
        raise RuntimeError(f"Expected 535 unique tickers, got {len(ordered_tickers)}")

    valid = {} if args.skip_probe else asyncio.run(probe(categories))
    indicators: list[dict[str, Any]] = []
    canonical_by_ticker: dict[str, str] = {}
    for ticker in ordered_tickers:
        override = overrides.get(ticker, {})
        route = routes.get(ticker)
        canonical_code = str(override.get("canonical_code") or f"US.TV.{ticker}")
        canonical_by_ticker[ticker] = canonical_code
        metadata = valid.get(ticker, {})
        frequency_code = str(metadata.get("frequency_code") or "M")
        unit = str(metadata.get("unit") or override.get("unit") or "VALUE")
        name_en = str(override.get("name_en") or readable_name(ticker, route))
        indicators.append(
            {
                "canonical_code": canonical_code,
                "name_zh": str(override.get("name_zh") or name_en),
                "name_en": name_en,
                "frequency": FREQUENCIES.get(
                    frequency_code,
                    str(override.get("frequency") or "月度"),
                ),
                "unit": unit,
                "theme": CATEGORIES[memberships[ticker][0]][1],
                "provider_series_id": f"ECONOMICS:US{ticker}",
                "route": route,
                "categories": memberships[ticker],
                "mapping_status": "READY" if ticker in valid else "CANDIDATE",
            }
        )

    nodes: list[dict[str, Any]] = [
        {
            "code": "tv-root",
            "parent_code": "root",
            "name_zh": "TradingView美国宏观",
            "name_en": "TradingView U.S. Macro",
            "node_type": "topic",
            "sort_order": 1,
            "series_codes": [],
        }
    ]
    category_by_id = {str(item["id"]): item for item in categories}
    for category_id, (node_code, name_zh, name_en, sort_order) in CATEGORIES.items():
        tickers = [str(item) for item in category_by_id[category_id]["tickers"]]
        nodes.append(
            {
                "code": node_code,
                "parent_code": "tv-root",
                "name_zh": name_zh,
                "name_en": name_en,
                "node_type": "group",
                "sort_order": sort_order,
                "series_codes": [canonical_by_ticker[ticker] for ticker in tickers],
            }
        )

    payload = {
        "tree_code": "macro-default",
        "extension_prefix": "tv-",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_indicator_route_count": int(catalog["indicatorRouteCount"]),
        "indicator_count": len(indicators),
        "valid_indicator_count": len(valid),
        "indicators": indicators,
        "nodes": nodes,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {args.output}: {len(indicators)} indicators, {len(valid)} ready",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
