#!/usr/bin/env python3
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

taxonomy_module = importlib.import_module(
    "macrolens_worker.providers.tradingview_taxonomy"
)
FED_DOMAINS = taxonomy_module.FED_DOMAINS
FED_TOPICS = taxonomy_module.FED_TOPICS


OFFICIAL_SERIES_BY_TOPIC: dict[str, tuple[str, ...]] = {
    "tv-fed-policy-rates": ("US.FED.FUNDS",),
    "tv-fed-policy-operations": ("US.REVERSE.REPO",),
    "tv-fed-central-bank-balance-sheet": (
        "US.FED.ASSETS",
        "US.BANK.RESERVES",
        "US.FED.MBS",
    ),
    "tv-fed-rate-transmission": ("US.SOFR",),
    "tv-fed-headline-inflation": ("US.CPI.HEADLINE",),
    "tv-fed-core-inflation": ("US.CPI.CORE",),
    "tv-fed-inflation-pce": (
        "US.PCE.HEADLINE",
        "US.PCE.CORE",
        "US.PCE.CORE.GOODS",
        "US.PCE.CORE.SERVICES",
        "US.PCE.NONHOUSING",
        "US.PCE.MEDICAL",
        "US.PCE.HOSPITAL",
        "US.PCE.PHYSICIAN",
        "US.PCE.OTHER.PROFESSIONAL",
        "US.PCE.DENTAL",
        "US.PCE.MEDICAL.EQUIPMENT",
        "US.PCE.PRESCRIPTION",
        "US.PCE.HEALTH.INSURANCE",
        "US.PCE.LONGTERM.CARE",
        "US.PCE.TRANSPORT",
        "US.PCE.RECREATION",
        "US.PCE.FOOD.SERVICES",
        "US.PCE.FINANCE",
        "US.PCE.OTHER.SERVICES",
        "US.PCE.DURABLES",
        "US.PCE.NONDURABLES",
    ),
    "tv-fed-inflation-components": ("US.CPI.MEDICAL",),
    "tv-fed-inflation-housing": (
        "US.PCE.HOUSING",
        "US.CPI.SHELTER",
    ),
    "tv-fed-inflation-pipeline": (
        "US.PPI.FINAL",
        "US.PPI.CORE",
    ),
    "tv-fed-inflation-expectations": (
        "US.BREAKEVEN.5Y5Y",
        "US.MICHIGAN.1Y",
    ),
    "tv-fed-growth-gdp": ("US.REAL.GDP",),
    "tv-fed-consumption-demand": (
        "US.RETAIL.SALES",
        "US.PERSONAL.CONSUMPTION",
    ),
    "tv-fed-production-capacity": ("US.INDUSTRIAL.PRODUCTION",),
    "tv-fed-orders-inventories-sales": ("US.DURABLE.ORDERS",),
    "tv-fed-labor-employment": ("US.PAYROLLS",),
    "tv-fed-labor-demand": ("US.JOB.OPENINGS",),
    "tv-fed-labor-separations": ("US.INITIAL.CLAIMS",),
    "tv-fed-labor-supply": ("US.PARTICIPATION",),
    "tv-fed-labor-unemployment": ("US.UNEMPLOYMENT",),
    "tv-fed-labor-wages": (
        "US.AVERAGE.HOURLY",
        "US.ECI",
    ),
    "tv-fed-business-credit": ("US.BANK.CREDIT",),
    "tv-fed-consumer-credit": ("US.CONSUMER.CREDIT",),
    "tv-fed-credit-pricing-standards": ("US.SLOOS",),
    "tv-fed-credit-quality": ("US.CARD.DELINQUENCY",),
    "tv-fed-riskfree-yield-curve": (
        "US.TREASURY.2Y",
        "US.TREASURY.10Y",
        "US.REAL.10Y",
    ),
    "tv-fed-credit-spreads": (
        "US.FINANCIAL.CONDITIONS",
        "US.CORPORATE.SPREAD",
    ),
    "tv-fed-fx-dollar": ("US.DOLLAR.INDEX",),
    "tv-fed-equity-volatility-risk": ("US.SP500",),
    "tv-fed-commodity-energy-markets": ("US.WTI",),
    "tv-fed-mortgage-market": ("US.MORTGAGE.30Y",),
}


def main() -> int:
    output = ROOT / "database" / "seed" / "taxonomy_registry.json"
    all_series = [
        canonical_code
        for series_codes in OFFICIAL_SERIES_BY_TOPIC.values()
        for canonical_code in series_codes
    ]
    if len(all_series) != 61 or len(set(all_series)) != 61:
        raise RuntimeError(
            "Federal Reserve taxonomy must own exactly 61 official series"
        )
    known_topics = {topic.code for topic in FED_TOPICS}
    unknown_topics = set(OFFICIAL_SERIES_BY_TOPIC) - known_topics
    if unknown_topics:
        raise RuntimeError(
            f"Unknown Federal Reserve taxonomy topics: {sorted(unknown_topics)}"
        )

    nodes = [
        {
            "code": "root",
            "parent_code": None,
            "name_zh": "美国宏观与金融体系",
            "name_en": "U.S. Macro and Financial System",
            "node_type": "category",
            "sort_order": 0,
            "series_codes": [],
        },
        *[
            {
                "code": domain.code,
                "parent_code": "root",
                "name_zh": domain.name_zh,
                "name_en": domain.name_en,
                "node_type": "topic",
                "sort_order": domain.sort_order,
                "series_codes": [],
            }
            for domain in FED_DOMAINS
        ],
        *[
            {
                "code": topic.code,
                "parent_code": topic.parent_code,
                "name_zh": topic.name_zh,
                "name_en": topic.name_en,
                "node_type": "group",
                "sort_order": topic.sort_order,
                "series_codes": list(OFFICIAL_SERIES_BY_TOPIC.get(topic.code, ())),
            }
            for topic in FED_TOPICS
        ],
    ]
    payload = {
        "tree_code": "macro-default",
        "expected_series_count": 61,
        "nodes": nodes,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {output}: {len(nodes)} nodes, {len(all_series)} official series")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
