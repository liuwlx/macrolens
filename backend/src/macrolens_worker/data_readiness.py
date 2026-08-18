from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from macrolens_api.config import Settings, get_settings
from macrolens_worker.tasks.sync import ADAPTERS


@dataclass(frozen=True, slots=True)
class IndicatorReadiness:
    canonical_code: str
    provider: str
    mapping_status: str
    status: str
    blockers: list[str]


def audit_source_registry(
    registry_path: Path,
    settings: Settings | None = None,
    *,
    check_credentials: bool = True,
) -> dict[str, Any]:
    configuration = settings or get_settings()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    rows: list[IndicatorReadiness] = []
    for item in registry.get("indicators", []):
        provider = str(item.get("recommended_source") or "")
        mapping_status = str(item.get("mapping_status") or "UNKNOWN")
        locator = item.get("locator") or {}
        blockers: list[str] = []
        if provider not in ADAPTERS:
            blockers.append("no_production_adapter")
        if mapping_status != "READY":
            blockers.append(f"mapping_status:{mapping_status}")
        if mapping_status in {"LICENSE_REQUIRED", "LEGAL_REVIEW_REQUIRED"}:
            blockers.append("license_or_legal_approval_required")
        blockers.extend(
            _provider_blockers(
                provider, item, locator, configuration, check_credentials=check_credentials
            )
        )
        status = "ready" if not blockers else _status_from_blockers(blockers)
        rows.append(
            IndicatorReadiness(
                canonical_code=str(item.get("canonical_code") or item.get("id")),
                provider=provider,
                mapping_status=mapping_status,
                status=status,
                blockers=sorted(set(blockers)),
            )
        )
    counts = Counter(row.status for row in rows)
    enabled_rows = [row for row in rows if row.mapping_status == "READY"]
    enabled_ready_count = sum(1 for row in enabled_rows if row.status == "ready")
    provider_counts: dict[str, Counter[str]] = {}
    for row in rows:
        provider_counts.setdefault(row.provider, Counter())[row.status] += 1
    return {
        "registry_generated_at": registry.get("generated_at"),
        "credential_checks_enabled": check_credentials,
        "indicator_count": len(rows),
        "ready_count": counts.get("ready", 0),
        "blocked_count": len(rows) - counts.get("ready", 0),
        "enabled_indicator_count": len(enabled_rows),
        "enabled_ready_count": enabled_ready_count,
        "enabled_blocked_count": len(enabled_rows) - enabled_ready_count,
        "all_enabled_ready": len(enabled_rows) > 0 and enabled_ready_count == len(enabled_rows),
        "all_production_ready": len(rows) > 0 and counts.get("ready", 0) == len(rows),
        "status_counts": dict(sorted(counts.items())),
        "provider_counts": {
            provider: dict(sorted(values.items()))
            for provider, values in sorted(provider_counts.items())
        },
        "indicators": [asdict(row) for row in rows],
    }


def _status_from_blockers(blockers: list[str]) -> str:
    joined = " ".join(blockers)
    if "license" in joined or "legal" in joined:
        return "blocked_license"
    if "no_production_adapter" in blockers:
        return "blocked_adapter"
    if any(blocker.startswith("credential:") for blocker in blockers):
        return "blocked_credentials"
    return "blocked_mapping"


def _provider_blockers(
    provider: str,
    item: dict[str, Any],
    locator: dict[str, Any],
    settings: Settings,
    *,
    check_credentials: bool,
) -> list[str]:
    blockers: list[str] = []
    provider_series_id = item.get("provider_series_id")
    credential_checks = {
        "BEA_API": (settings.bea_api_key, "BEA_API_KEY"),
        "BLS_API_V2": (settings.bls_api_key, "BLS_API_KEY"),
        "FRED_API": (settings.fred_api_key, "FRED_API_KEY"),
        "EIA_API_V2": (settings.eia_api_key, "EIA_API_KEY"),
        "CENSUS_EITS_API": (settings.census_api_key, "CENSUS_API_KEY"),
        "DOL_OPEN_DATA_API": (settings.dol_claims_url or locator.get("url"), "DOL_CLAIMS_URL"),
    }
    if check_credentials and provider in credential_checks and not credential_checks[provider][0]:
        blockers.append(f"credential:{credential_checks[provider][1]}")

    if provider == "BEA_API":
        if not locator.get("table_name"):
            blockers.append("locator:table_name")
        if not any(
            locator.get(key)
            for key in (
                "series_code",
                "line_number",
                "line_match",
                "target_description_en",
                "line_aliases",
            )
        ):
            blockers.append("locator:verified_line_identity")
    elif provider == "BLS_API_V2":
        if not provider_series_id:
            blockers.append("locator:provider_series_id")
        if not (locator.get("expected_first_period") or locator.get("start_year")):
            blockers.append("locator:history_start")
    elif provider == "FRED_API":
        if not provider_series_id:
            blockers.append("locator:provider_series_id")
        if not (locator.get("expected_first_period") or locator.get("observation_start")):
            # FRED metadata can discover the start dynamically, but a production mapping must
            # pin the expected history boundary so a provider-side truncation is detectable.
            blockers.append("locator:history_start")
    elif provider == "CENSUS_EITS_API":
        if locator.get("resolve_dimensions_from_dictionary") or not locator.get("dimensions"):
            blockers.append("locator:approved_dimensions")
    elif provider == "DOL_OPEN_DATA_API":
        if not locator.get("date_field"):
            blockers.append("locator:date_field")
        if not locator.get("value_field"):
            blockers.append("locator:value_field")
        pagination = locator.get("pagination") or {}
        if not (bool(pagination.get("enabled")) or bool(locator.get("complete_snapshot"))):
            blockers.append("locator:pagination_or_complete_snapshot")
    elif provider == "EIA_API_V2":
        if not locator.get("route"):
            blockers.append("locator:route")
        if not locator.get("expected_first_period"):
            blockers.append("locator:history_start")
    elif provider == "FED_BOARD_FILES":
        if not locator.get("file_url"):
            blockers.append("locator:file_url")
        if not locator.get("format"):
            blockers.append("locator:format")
        if not locator.get("series_code"):
            blockers.append("locator:series_code")
        if not locator.get("line_description"):
            blockers.append("locator:line_description")
        if not locator.get("expected_first_period"):
            blockers.append("locator:history_start")
    elif provider == "NYFED_MARKETS_API":
        if not locator.get("route"):
            blockers.append("locator:route")
        if not (locator.get("expected_first_period") or locator.get("start_date")):
            blockers.append("locator:history_start")
        if provider_series_id == "RRP_TOTAL_ACCEPTED":
            params = locator.get("params") or {}
            if str(locator.get("field") or "") != "totalAmtAccepted":
                blockers.append("locator:rrp_total_field")
            if str(locator.get("aggregation") or "") != "sum":
                blockers.append("locator:rrp_aggregation")
            if params.get("operationTypes") != "reverserepo":
                blockers.append("locator:rrp_operation_type")
            if params.get("securityType") != "tsy":
                blockers.append("locator:rrp_security_type")
            if params.get("term") != "Overnight":
                blockers.append("locator:rrp_term")
    elif provider == "US_TREASURY_XML":
        if not provider_series_id:
            blockers.append("locator:provider_series_id")
        if not locator.get("start_year"):
            blockers.append("locator:start_year")
        if not locator.get("expected_first_period"):
            blockers.append("locator:history_start")
    return blockers
