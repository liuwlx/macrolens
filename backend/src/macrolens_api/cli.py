from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import typer
from sqlalchemy import select

from .catalog_registry import get_catalog_registry
from .config import get_settings
from .db import SessionLocal
from .models import (
    Dataset,
    Job,
    LicensePolicy,
    Provider,
    ReleaseDefinition,
    Series,
    SeriesAlias,
    SourceSeries,
    TaxonomyNode,
    TaxonomySeries,
    User,
    Workspace,
)
from .security import hash_password
from .services.jobs import enqueue_job
from .services.source_mapping_identity import source_mapping_fingerprint

app = typer.Typer(no_args_is_help=True)
settings = get_settings()

PROVIDERS: dict[str, dict[str, Any]] = {
    "FEDERAL_RESERVE": {
        "name": "Board of Governors of the Federal Reserve System",
        "type": "central_bank",
        "base_url": "https://www.federalreserve.gov",
        "docs": "https://www.federalreserve.gov/monetarypolicy.htm",
        "license": "US_GOV_PUBLIC",
        "redistribution": True,
        "attribution": "Board of Governors of the Federal Reserve System",
    },
    "FRED_API": {
        "name": "Federal Reserve Economic Data (FRED)",
        "type": "central_bank",
        "base_url": "https://api.stlouisfed.org",
        "docs": "https://fred.stlouisfed.org/docs/api/fred/",
        "license": "PUBLIC_WITH_TERMS",
        "redistribution": False,
        "attribution": "Federal Reserve Bank of St. Louis and the original data provider",
    },
    "BEA_API": {
        "name": "U.S. Bureau of Economic Analysis",
        "type": "government",
        "base_url": "https://apps.bea.gov/api/data",
        "docs": "https://apps.bea.gov/api/",
        "license": "US_GOV_PUBLIC",
        "redistribution": True,
        "attribution": "U.S. Bureau of Economic Analysis",
    },
    "BLS_API_V2": {
        "name": "U.S. Bureau of Labor Statistics",
        "type": "government",
        "base_url": "https://api.bls.gov/publicAPI/v2",
        "docs": "https://www.bls.gov/developers/",
        "license": "US_GOV_PUBLIC_ATTRIBUTION",
        "redistribution": True,
        "attribution": "U.S. Bureau of Labor Statistics",
    },
    "CENSUS_EITS_API": {
        "name": "U.S. Census Bureau",
        "type": "government",
        "base_url": "https://api.census.gov/data/timeseries/eits",
        "docs": "https://www.census.gov/data/developers/data-sets/economic-indicators.html",
        "license": "US_GOV_PUBLIC_ATTRIBUTION",
        "redistribution": True,
        "attribution": "U.S. Census Bureau",
    },
    "DOL_OPEN_DATA_API": {
        "name": "U.S. Department of Labor",
        "type": "government",
        "base_url": "https://data.dol.gov",
        "docs": "https://www.dol.gov/agencies/oasam/centers-offices/ocio/data",
        "license": "US_GOV_PUBLIC",
        "redistribution": True,
        "attribution": "U.S. Department of Labor",
    },
    "EIA_API_V2": {
        "name": "U.S. Energy Information Administration",
        "type": "government",
        "base_url": "https://api.eia.gov/v2",
        "docs": "https://www.eia.gov/opendata/documentation.php",
        "license": "US_GOV_PUBLIC_ATTRIBUTION",
        "redistribution": True,
        "attribution": "U.S. Energy Information Administration",
    },
    "NYFED_MARKETS_API": {
        "name": "Federal Reserve Bank of New York Markets API",
        "type": "central_bank",
        "base_url": "https://markets.newyorkfed.org/api",
        "docs": "https://markets.newyorkfed.org/static/docs/markets-api.html",
        "license": "PUBLIC_WITH_TERMS",
        "redistribution": True,
        "attribution": "Federal Reserve Bank of New York",
    },
    "US_TREASURY_XML": {
        "name": "U.S. Department of the Treasury",
        "type": "government",
        "base_url": "https://home.treasury.gov",
        "docs": "https://home.treasury.gov/treasury-daily-interest-rate-xml-feed",
        "license": "US_GOV_PUBLIC",
        "redistribution": True,
        "attribution": "U.S. Department of the Treasury",
    },
    "UMICH_SURVEYS_OF_CONSUMERS": {
        "name": "University of Michigan Surveys of Consumers",
        "type": "academic",
        "base_url": "https://data.sca.isr.umich.edu",
        "docs": "https://data.sca.isr.umich.edu/",
        "license": "PUBLIC_WITH_TERMS",
        "redistribution": False,
        "attribution": "University of Michigan Surveys of Consumers",
    },
    "FREDDIE_MAC_PMMS": {
        "name": "Freddie Mac Primary Mortgage Market Survey",
        "type": "government",
        "base_url": "https://www.freddiemac.com/pmms",
        "docs": "https://www.freddiemac.com/pmms",
        "license": "THIRD_PARTY_RESTRICTED",
        "redistribution": False,
        "attribution": "Freddie Mac",
    },
    "ICE_DATA_LICENSED_FEED": {
        "name": "ICE Data Services",
        "type": "commercial",
        "base_url": None,
        "docs": None,
        "license": "COMMERCIAL",
        "redistribution": False,
        "attribution": "ICE Data Services",
    },
    "CME_FEDWATCH_LICENSED_API": {
        "name": "CME FedWatch Licensed API",
        "type": "commercial",
        "base_url": None,
        "docs": "https://www.cmegroup.com/market-data/market-data-api/fedwatch-api.html",
        "license": "COMMERCIAL",
        "redistribution": False,
        "attribution": "CME Group",
    },
    "LICENSED_MARKET_DATA_VENDOR": {
        "name": "Licensed Market Data Vendor",
        "type": "commercial",
        "base_url": None,
        "docs": None,
        "license": "COMMERCIAL",
        "redistribution": False,
        "attribution": None,
    },
}

FREQUENCY_MAP = {"日度": "daily", "周度": "weekly", "月度": "monthly", "季度": "quarterly"}
UNIT_MAP = {
    "%": ("percent", "%"),
    "百分点": ("percentage_point", "百分点"),
    "指数": ("index", "指数"),
    "千人": ("thousand_persons", "千人"),
    "十亿美元": ("billion_usd", "十亿美元"),
    "百万美元": ("million_usd", "百万美元"),
    "美元/小时": ("usd_per_hour", "美元/小时"),
    "美元/桶": ("usd_per_barrel", "美元/桶"),
    "标准差": ("standard_deviation", "标准差"),
}


def _theme(code: str) -> str:
    if any(token in code for token in ["PCE", "CPI", "PPI", "BREAKEVEN", "MICHIGAN"]):
        return "通胀"
    if any(
        token in code
        for token in [
            "PAYROLL",
            "UNEMPLOY",
            "PARTICIPATION",
            "HOURLY",
            "JOB.OPENINGS",
            "CLAIMS",
            "ECI",
        ]
    ):
        return "就业"
    if any(token in code for token in ["GDP", "RETAIL", "DURABLE", "INDUSTRIAL", "CONSUMPTION"]):
        return "增长"
    if any(
        token in code
        for token in [
            "FED.FUNDS",
            "SOFR",
            "TREASURY",
            "REAL.10Y",
            "FED.ASSETS",
            "RESERVES",
            "REVERSE.REPO",
            "FED.MBS",
        ]
    ):
        return "利率与政策"
    if any(token in code for token in ["BANK", "CREDIT", "DELINQUENCY", "SLOOS"]):
        return "信贷与银行"
    return "金融市场"


async def seed_all() -> None:
    registry = get_catalog_registry()
    async with SessionLocal() as session:
        provider_by_code: dict[str, Provider] = {}
        for code, item in PROVIDERS.items():
            provider = await session.scalar(select(Provider).where(Provider.code == code))
            if provider is None:
                provider = Provider(
                    code=code,
                    name=item["name"],
                    provider_type=item["type"],
                    base_url=item["base_url"],
                    api_docs_url=item["docs"],
                    attribution_text=item["attribution"],
                    license_class=item["license"],
                    redistribution_ok=item["redistribution"],
                    active=True,
                )
                session.add(provider)
                await session.flush()
            provider.name = item["name"]
            provider.provider_type = item["type"]
            provider.base_url = item["base_url"]
            provider.api_docs_url = item["docs"]
            provider.attribution_text = item["attribution"]
            provider.license_class = item["license"]
            provider.redistribution_ok = item["redistribution"]
            provider.active = True
            policy = await session.scalar(
                select(LicensePolicy).where(LicensePolicy.provider_id == provider.id)
            )
            if policy is None:
                policy = LicensePolicy(provider_id=provider.id)
                session.add(policy)
            policy.display_allowed = item["redistribution"] or code == "FRED_API"
            policy.download_allowed = item["redistribution"]
            policy.api_redistribution_allowed = item["redistribution"]
            policy.ai_context_allowed = item["redistribution"] or code == "FRED_API"
            policy.ai_training_allowed = False
            policy.attribution_required = True
            policy.attribution_text = item["attribution"]
            policy.restrictions = (
                "Review provider terms before enabling restricted or commercial data."
            )
            provider_by_code[code] = provider

        dataset_cache: dict[tuple[str, str], Dataset] = {}
        series_by_code: dict[str, Series] = {}
        for indicator in registry.indicators:
            item = indicator.payload
            provider = provider_by_code[item["recommended_source"]]
            dataset_code = str(item["dataset"] or "default")
            key = (provider.code, dataset_code)
            dataset = dataset_cache.get(key)
            if dataset is None:
                dataset = await session.scalar(
                    select(Dataset).where(
                        Dataset.provider_id == provider.id, Dataset.code == dataset_code
                    )
                )
                if dataset is None:
                    dataset = Dataset(
                        provider_id=provider.id,
                        code=dataset_code,
                        name=dataset_code,
                        endpoint_template=provider.base_url,
                        active=True,
                    )
                    session.add(dataset)
                    await session.flush()
                dataset.name = dataset_code
                dataset.endpoint_template = provider.base_url
                dataset.active = True
                dataset_cache[key] = dataset

            series = await session.scalar(
                select(Series).where(Series.canonical_code == item["canonical_code"])
            )
            unit_code, unit_label = UNIT_MAP.get(item["unit"], (item["unit"], item["unit"]))
            if series is None:
                series = Series(
                    canonical_code=item["canonical_code"],
                    name_zh=item["name_zh"],
                    name_en=item.get("name_en"),
                    short_name_zh=item["name_zh"],
                    description="；".join(item.get("notes") or []) or None,
                    theme=_theme(item["canonical_code"]),
                    series_type=("derived" if item.get("locator", {}).get("transform") else "raw"),
                    frequency=FREQUENCY_MAP[item["frequency"]],
                    unit_code=unit_code,
                    unit_label_zh=unit_label,
                    seasonal_adjustment=(item.get("seasonal_adjustment") or "not_specified"),
                    default_transform="level",
                    decimal_places=2,
                    status="active" if item["mapping_status"] == "READY" else "draft",
                )
                session.add(series)
                await session.flush()
            series.name_zh = item["name_zh"]
            series.name_en = item.get("name_en")
            series.short_name_zh = item["name_zh"]
            series.description = "；".join(item.get("notes") or []) or None
            series.theme = _theme(item["canonical_code"])
            series.series_type = "derived" if item.get("locator", {}).get("transform") else "raw"
            series.frequency = FREQUENCY_MAP[item["frequency"]]
            series.unit_code = unit_code
            series.unit_label_zh = unit_label
            series.seasonal_adjustment = item.get("seasonal_adjustment") or "not_specified"
            series.default_transform = "level"
            series.decimal_places = 2
            series.status = "active" if item["mapping_status"] == "READY" else "draft"
            for alias, language in (
                (item["name_zh"], "zh-CN"),
                (item.get("prototype_code"), "code"),
            ):
                if not alias:
                    continue
                existing_alias = await session.scalar(
                    select(SeriesAlias).where(
                        SeriesAlias.series_id == series.id,
                        SeriesAlias.alias == alias,
                        SeriesAlias.language == language,
                    )
                )
                if existing_alias is None:
                    session.add(SeriesAlias(series_id=series.id, alias=alias, language=language))
            series_by_code[series.canonical_code] = series

            source_series = await session.scalar(
                select(SourceSeries).where(
                    SourceSeries.series_id == series.id,
                    SourceSeries.dataset_id == dataset.id,
                )
            )
            if source_series is None:
                source_series = SourceSeries(
                    series_id=series.id,
                    dataset_id=dataset.id,
                )
                session.add(source_series)
            source_series.provider_series_id = item.get("provider_series_id")
            source_series.source_locator = item.get("locator") or {}
            source_series.mapping_type = (item.get("mapping_type") or "direct").lower()
            source_series.source_frequency = FREQUENCY_MAP[item["frequency"]]
            source_series.source_unit = item["unit"]
            source_series.source_title = item["name_en"] or item["name_zh"]
            source_series.notes = "; ".join(item.get("notes") or [])
            await session.flush()
            probe_job = (
                await session.get(Job, source_series.verification_job_id)
                if source_series.verification_job_id
                else None
            )
            fingerprint = source_mapping_fingerprint(source_series, dataset, provider)
            approval = probe_job.result.get("approval") if probe_job else None
            was_probe_approved = bool(
                probe_job is not None
                and source_series.mapping_status == "verified"
                and source_series.is_primary
                and probe_job.status == "succeeded"
                and probe_job.result.get("mapping_fingerprint") == fingerprint
                and source_series.verification_fingerprint == fingerprint
                and isinstance(approval, dict)
                and int(approval.get("source_series_id", -1)) == source_series.id
            )
            status = {
                "READY": "verified" if was_probe_approved else "needs_review",
                "LICENSE_REQUIRED": "license_required",
                "LEGAL_REVIEW_REQUIRED": "license_required",
            }.get(item["mapping_status"], "needs_review")
            source_series.mapping_status = status
            source_series.is_primary = was_probe_approved and status == "verified"
            if status != "verified":
                source_series.verified_by = None
                source_series.verified_at = None
                source_series.verification_job_id = None
                source_series.verification_fingerprint = None

        desired_node_codes = {node.code for node in registry.nodes}
        legacy_nodes = list(
            (
                await session.scalars(
                    select(TaxonomyNode).where(
                        TaxonomyNode.tree_code == registry.tree_code,
                        TaxonomyNode.code.not_in(desired_node_codes),
                    )
                )
            ).all()
        )
        for legacy_node in legacy_nodes:
            legacy_node.visible = False

        nodes_by_code: dict[str, TaxonomyNode] = {}
        ordered_nodes = sorted(registry.nodes, key=lambda node: len(registry.node_path(node)))
        for node_spec in ordered_nodes:
            node = await session.scalar(
                select(TaxonomyNode).where(
                    TaxonomyNode.tree_code == registry.tree_code,
                    TaxonomyNode.code == node_spec.code,
                )
            )
            if node is None:
                node = TaxonomyNode(tree_code=registry.tree_code, code=node_spec.code)
                session.add(node)
            node.parent_id = (
                nodes_by_code[node_spec.parent_code].id
                if node_spec.parent_code is not None
                else None
            )
            node.node_type = node_spec.node_type
            node.name_zh = node_spec.name_zh
            node.name_en = node_spec.name_en
            node.sort_order = node_spec.sort_order
            node.icon_key = node_spec.icon_key
            node.visible = True
            node.status = "active"
            await session.flush()
            nodes_by_code[node_spec.code] = node

        current_mappings = list(
            (
                await session.scalars(
                    select(TaxonomySeries).where(
                        TaxonomySeries.node_id.in_([node.id for node in nodes_by_code.values()])
                    )
                )
            ).all()
        )
        for mapping in current_mappings:
            mapping.display_role = "detail"
            mapping.is_primary = False

        for node_spec in ordered_nodes:
            node = nodes_by_code[node_spec.code]
            for display_order, canonical_code in enumerate(node_spec.series_codes):
                series = series_by_code[canonical_code]
                taxonomy_mapping = await session.scalar(
                    select(TaxonomySeries).where(
                        TaxonomySeries.node_id == node.id,
                        TaxonomySeries.series_id == series.id,
                    )
                )
                if taxonomy_mapping is None:
                    taxonomy_mapping = TaxonomySeries(node_id=node.id, series_id=series.id)
                    session.add(taxonomy_mapping)
                taxonomy_mapping.display_role = "primary"
                taxonomy_mapping.display_order = display_order
                taxonomy_mapping.is_primary = True

        for code, name in [
            ("PCE", "个人收入与支出"),
            ("CPI", "消费者价格指数"),
            ("PPI", "生产者价格指数"),
            ("EMPLOYMENT", "就业形势"),
            ("ECI", "就业成本指数"),
            ("JOLTS", "职位空缺与劳动力流动"),
            ("FOMC", "FOMC会议"),
        ]:
            provider = provider_by_code[
                "BEA_API"
                if code == "PCE"
                else "BLS_API_V2"
                if code in {"CPI", "PPI", "EMPLOYMENT", "ECI", "JOLTS"}
                else "FEDERAL_RESERVE"
            ]
            existing = await session.scalar(
                select(ReleaseDefinition).where(ReleaseDefinition.code == code)
            )
            if existing is None:
                session.add(
                    ReleaseDefinition(
                        code=code,
                        provider_id=provider.id,
                        name_zh=name,
                        release_type="meeting" if code == "FOMC" else "data",
                        source_timezone="America/New_York",
                    )
                )

        admin = await session.scalar(
            select(User).where(User.email == settings.bootstrap_admin_email.lower())
        )
        if admin is None:
            admin = User(
                email=settings.bootstrap_admin_email.lower(),
                display_name="MacroLens Admin",
                password_hash=hash_password(settings.bootstrap_admin_password),
                role="admin",
            )
            session.add(admin)
            await session.flush()
            session.add(Workspace(name="MacroLens Admin Workspace", owner_user_id=admin.id))
        await session.commit()


@app.command("seed")
def seed() -> None:
    """Seed providers, catalog mappings, taxonomy and the bootstrap admin."""
    asyncio.run(seed_all())
    typer.echo("Seed completed.")


@app.command("seed-test-fixtures")
def seed_test_fixtures() -> None:
    """Seed deterministic acceptance data. Refuses to run unless explicitly enabled."""
    from .test_fixtures import seed_runtime_acceptance_fixtures

    async def _seed() -> dict[str, int | str]:
        async with SessionLocal() as session:
            return await seed_runtime_acceptance_fixtures(session)

    result = asyncio.run(_seed())
    typer.echo(json.dumps(result, ensure_ascii=False))


@app.command("enqueue-sync")
def enqueue_sync(
    provider: str = typer.Option(..., help="Provider code, for example FRED_API"),
) -> None:
    async def _enqueue() -> None:
        async with SessionLocal() as session:
            await enqueue_job(
                session,
                job_type="sync_provider",
                payload={"provider_code": provider},
                idempotency_key=f"manual-sync:{provider}:{datetime.now(UTC).strftime('%Y%m%d%H%M')}",
                priority=10,
            )

    asyncio.run(_enqueue())
    typer.echo(f"Sync job queued for {provider}.")


if __name__ == "__main__":
    app()
