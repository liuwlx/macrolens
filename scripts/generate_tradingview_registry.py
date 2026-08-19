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
tradingview_name_zh: Any = importlib.import_module(
    "macrolens_worker.providers.tradingview_names"
).tradingview_name_zh
taxonomy_module = importlib.import_module(
    "macrolens_worker.providers.tradingview_taxonomy"
)
FED_DOMAINS: Any = taxonomy_module.FED_DOMAINS
FED_DOMAIN_BY_CODE: Any = taxonomy_module.FED_DOMAIN_BY_CODE
FED_TOPICS: Any = taxonomy_module.FED_TOPICS
FED_TOPIC_BY_CODE: Any = taxonomy_module.FED_TOPIC_BY_CODE
classify_tradingview_indicator: Any = taxonomy_module.classify_tradingview_indicator

FREQUENCIES = {
    "D": "日度",
    "W": "周度",
    "M": "月度",
    "3M": "季度",
    "12M": "年度",
}
FREQUENCY_CODES = {label: code for code, label in FREQUENCIES.items()}


def route_map(js_source: str) -> dict[str, str | None]:
    matches = re.finditer(
        r'\{ticker:"(?P<ticker>[^"]+)",name:.*?,route:(?:"(?P<route>[^"]*)"|null)',
        js_source,
    )
    return {match.group("ticker"): match.group("route") or None for match in matches}


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
) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
    valid: dict[str, dict[str, str]] = {}
    unavailable_us: dict[str, dict[str, str]] = {}
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
        adapter = TradingViewAdapter(client=None)  # type: ignore[arg-type]
        for attempt in range(1, 4):
            try:
                results = await adapter.fetch(
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
            raise RuntimeError(
                f"TradingView probe returned no result for {category['id']}"
            )
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
        for ticker in tickers:
            symbol = f"ECONOMICS:US{ticker}"
            if adapter.symbol_errors.get(symbol) == "no_such_symbol":
                unavailable_us[ticker] = {
                    "code": "no_such_symbol",
                    "geography": "US",
                }
        print(
            f"{category['id']}: {len(observations)}/{len(tickers)} valid, "
            f"{sum(ticker in unavailable_us for ticker in tickers)} unavailable for US",
            file=sys.stderr,
            flush=True,
        )
        await asyncio.sleep(0.25)
    return valid, unavailable_us


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

    if args.skip_probe:
        valid = {
            ticker: {
                "frequency_code": FREQUENCY_CODES.get(
                    str(item.get("frequency") or "月度"),
                    "M",
                ),
                "unit": str(item.get("unit") or "VALUE"),
            }
            for ticker, item in overrides.items()
            if item.get("mapping_status") == "READY"
        }
        unavailable_us = {
            ticker: dict(item.get("availability_evidence") or {})
            for ticker, item in overrides.items()
            if item.get("mapping_status") == "UNAVAILABLE_US"
        }
    else:
        valid, unavailable_us = asyncio.run(probe(categories))
    indicators: list[dict[str, Any]] = []
    series_by_topic: dict[str, list[str]] = {topic.code: [] for topic in FED_TOPICS}
    for ticker in ordered_tickers:
        override = overrides.get(ticker, {})
        route = routes.get(ticker)
        canonical_code = str(override.get("canonical_code") or f"US.TV.{ticker}")
        metadata = valid.get(ticker, {})
        frequency_code = str(metadata.get("frequency_code") or "")
        unit = str(metadata.get("unit") or override.get("unit") or "VALUE")
        name_en = str(override.get("name_en") or readable_name(ticker, route))
        mapping_status = (
            "READY"
            if ticker in valid
            else "UNAVAILABLE_US"
            if ticker in unavailable_us
            else "READY"
            if override.get("mapping_status") == "READY"
            else "CANDIDATE"
        )
        source_categories = tuple(memberships[ticker])
        assignment = classify_tradingview_indicator(
            ticker=ticker,
            name=name_en,
            route=route,
            source_categories=source_categories,
        )
        topic = FED_TOPIC_BY_CODE[assignment.primary_topic]
        domain = FED_DOMAIN_BY_CODE[topic.parent_code]
        indicator: dict[str, Any] = {
            "canonical_code": canonical_code,
            "name_zh": tradingview_name_zh(
                canonical_code,
                name_en,
                str(override.get("name_zh") or "") or None,
            ),
            "name_en": name_en,
            "frequency": FREQUENCIES.get(
                frequency_code,
                str(override.get("frequency") or "月度"),
            ),
            "unit": unit,
            "theme": domain.name_zh,
            "provider_series_id": f"ECONOMICS:US{ticker}",
            "route": route,
            "categories": list(source_categories),
            "source_categories": list(source_categories),
            "primary_topic": assignment.primary_topic,
            "cross_tags": list(assignment.cross_tags),
            "mapping_status": mapping_status,
        }
        if mapping_status == "UNAVAILABLE_US":
            indicator["availability_evidence"] = unavailable_us[ticker]
        indicators.append(indicator)
        series_by_topic[assignment.primary_topic].append(canonical_code)

    nodes: list[dict[str, Any]] = [
        {
            "code": topic.code,
            "parent_code": topic.parent_code,
            "name_zh": topic.name_zh,
            "name_en": topic.name_en,
            "node_type": "group",
            "sort_order": topic.sort_order,
            "series_codes": series_by_topic[topic.code],
        }
        for topic in FED_TOPICS
    ]

    ready_count = sum(item["mapping_status"] == "READY" for item in indicators)
    payload = {
        "tree_code": "macro-default",
        "extension_prefix": "tv-",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_indicator_route_count": int(catalog["indicatorRouteCount"]),
        "indicator_count": len(indicators),
        "valid_indicator_count": ready_count,
        "unavailable_us_indicator_count": len(unavailable_us),
        "framework_domains": [
            {
                "code": domain.code,
                "name_zh": domain.name_zh,
                "name_en": domain.name_en,
                "sort_order": domain.sort_order,
            }
            for domain in FED_DOMAINS
        ],
        "indicators": indicators,
        "nodes": nodes,
    }
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {args.output}: {len(indicators)} indicators, {ready_count} ready, "
        f"{len(unavailable_us)} unavailable for US",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
