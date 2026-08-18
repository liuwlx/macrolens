from __future__ import annotations

import calendar
import re
from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any, Literal
from urllib.parse import urlsplit, urlunsplit

import httpx

from macrolens_api.models import Dataset, Provider, SourceSeries


class ProviderDataError(RuntimeError):
    """Raised when an upstream response is syntactically valid but not safe to publish."""


@dataclass(frozen=True, slots=True)
class NormalizedObservation:
    source_series_id: int
    period_start: date
    period_end: date
    value: Decimal | None
    value_text: str | None = None
    status: str = "normal"
    published_at: datetime | None = None
    vintage_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_updated_at: datetime | None = None
    quality_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProviderFetchResult:
    provider: Provider
    dataset: Dataset | None
    request_url: str
    request_parameters: dict[str, Any]
    content_type: str
    raw_bytes: bytes
    observations: list[NormalizedObservation]
    source_last_modified: datetime | None = None
    captured_at: datetime | None = None
    persist_raw: bool = True


@dataclass(frozen=True, slots=True)
class MappingProbeEvidence:
    transport_success: bool
    http_success: bool
    business_success: bool
    identity_match: bool
    authorization_available: bool
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MappingProbeIssue:
    stage: Literal["configuration", "transport", "http", "business", "identity", "authorization"]
    code: str
    message: str
    blocking: bool = True


@dataclass(frozen=True, slots=True)
class MappingProbeResult:
    """Read-only evidence for deciding whether a source mapping may be approved."""

    provider_code: str
    source_series_id: int
    provider_series_id: str | None
    request_url: str
    http_reachable: bool
    http_status: int | None
    content_type: str
    business_success: bool
    identity_match: bool
    official_description: str
    response_sha256: str
    probed_at: datetime
    authorization_available: bool
    production_ready: bool
    classification: Literal["PASS", "AUTH_REQUIRED", "BLOCKED"]
    evidence: MappingProbeEvidence | None = None
    issues: tuple[MappingProbeIssue, ...] = ()

    def __post_init__(self) -> None:
        if urlsplit(self.request_url).query:
            raise ValueError("MappingProbeResult.request_url must not contain a query")
        evidence = self.evidence
        if evidence is None:
            evidence = MappingProbeEvidence(
                transport_success=self.http_reachable,
                http_success=(
                    self.http_reachable
                    and self.http_status is not None
                    and 200 <= self.http_status < 300
                ),
                business_success=self.business_success,
                identity_match=self.identity_match,
                authorization_available=self.authorization_available,
            )
            object.__setattr__(self, "evidence", evidence)
        expected_old_fields = (
            evidence.transport_success,
            evidence.business_success,
            evidence.identity_match,
            evidence.authorization_available,
        )
        if expected_old_fields != (
            self.http_reachable,
            self.business_success,
            self.identity_match,
            self.authorization_available,
        ):
            raise ValueError("MappingProbeResult evidence contradicts legacy fields")
        expected_http_success = (
            self.http_reachable and self.http_status is not None and 200 <= self.http_status < 300
        )
        if evidence.http_success != expected_http_success:
            raise ValueError("MappingProbeResult HTTP evidence contradicts status")
        if (
            (
                not evidence.transport_success
                and any((evidence.http_success, evidence.business_success, evidence.identity_match))
            )
            or (
                not evidence.http_success
                and any((evidence.business_success, evidence.identity_match))
            )
            or (not evidence.business_success and evidence.identity_match)
        ):
            raise ValueError("MappingProbeResult evidence violates probe-stage causality")
        if not self.issues:
            inferred_issues: list[MappingProbeIssue] = []
            if not evidence.transport_success:
                inferred_issues.append(
                    MappingProbeIssue(
                        "transport",
                        "transport_error",
                        "Provider request was unreachable",
                    )
                )
            elif not evidence.http_success:
                inferred_issues.append(
                    MappingProbeIssue("http", "http_status", "Provider returned a non-2xx status")
                )
            elif not evidence.business_success:
                inferred_issues.append(
                    MappingProbeIssue(
                        "business",
                        "business_error",
                        "Provider response did not report business success",
                    )
                )
            elif not evidence.identity_match:
                inferred_issues.append(
                    MappingProbeIssue(
                        "identity",
                        "identity_mismatch",
                        "Provider response did not match the pinned identity",
                    )
                )
            if not evidence.authorization_available:
                inferred_issues.append(
                    MappingProbeIssue(
                        "authorization",
                        "authorization_missing",
                        "Provider API authorization is unavailable",
                    )
                )
            if inferred_issues:
                object.__setattr__(self, "issues", tuple(inferred_issues))
        classification = _classify_mapping_probe(evidence, self.issues)
        if classification != self.classification:
            raise ValueError("MappingProbeResult classification contradicts evidence and issues")
        if self.production_ready != (classification == "PASS"):
            raise ValueError("MappingProbeResult production_ready contradicts classification")

    def to_dict(self) -> dict[str, Any]:
        serialized = asdict(self)
        serialized["probed_at"] = self.probed_at.isoformat()
        serialized["issues"] = [asdict(issue) for issue in self.issues]
        return serialized


def _classify_mapping_probe(
    evidence: MappingProbeEvidence,
    issues: tuple[MappingProbeIssue, ...],
) -> Literal["PASS", "AUTH_REQUIRED", "BLOCKED"]:
    blocking_non_auth = any(issue.blocking and issue.stage != "authorization" for issue in issues)
    verified_without_auth = (
        evidence.transport_success
        and evidence.http_success
        and evidence.business_success
        and evidence.identity_match
        and not blocking_non_auth
    )
    if (
        verified_without_auth
        and evidence.authorization_available
        and not any(issue.blocking for issue in issues)
    ):
        return "PASS"
    if verified_without_auth and not evidence.authorization_available:
        return "AUTH_REQUIRED"
    return "BLOCKED"


def _build_mapping_probe_result(
    *,
    provider_code: str,
    source_series_id: int,
    provider_series_id: str | None,
    request_url: str,
    http_status: int | None,
    content_type: str,
    official_description: str,
    response_sha256: str,
    probed_at: datetime,
    evidence: MappingProbeEvidence,
    issues: tuple[MappingProbeIssue, ...] = (),
) -> MappingProbeResult:
    classification = _classify_mapping_probe(evidence, issues)
    return MappingProbeResult(
        provider_code=provider_code,
        source_series_id=source_series_id,
        provider_series_id=provider_series_id,
        request_url=request_url,
        http_reachable=evidence.transport_success,
        http_status=http_status,
        content_type=content_type,
        business_success=evidence.business_success,
        identity_match=evidence.identity_match,
        official_description=official_description,
        response_sha256=response_sha256,
        probed_at=probed_at,
        authorization_available=evidence.authorization_available,
        production_ready=classification == "PASS",
        classification=classification,
        evidence=evidence,
        issues=issues,
    )


_SENSITIVE_PARAMETER_NAMES = {
    "apikey",
    "key",
    "registrationkey",
    "userid",
}


def _is_sensitive_name(value: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(value).lower())
    return (
        normalized in _SENSITIVE_PARAMETER_NAMES
        or normalized.endswith("apikey")
        or normalized.endswith("authorization")
    )


def _redact_sensitive_data(value: Any, *, secrets: tuple[str, ...] = ()) -> Any:
    """Remove credential fields and values from persistable provider evidence."""

    if isinstance(value, dict):
        return {
            key: _redact_sensitive_data(item, secrets=secrets)
            for key, item in value.items()
            if not _is_sensitive_name(key)
        }
    if isinstance(value, list):
        return [_redact_sensitive_data(item, secrets=secrets) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_sensitive_data(item, secrets=secrets) for item in value)
    if isinstance(value, str):
        sanitized = value
        for secret in secrets:
            if secret:
                sanitized = sanitized.replace(secret, "[REDACTED]")
        return sanitized
    if isinstance(value, bytes):
        sanitized_bytes = value
        for secret in secrets:
            if secret:
                sanitized_bytes = sanitized_bytes.replace(secret.encode(), b"[REDACTED]")
        return sanitized_bytes
    return value


def _strip_url_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def _raise_for_status_safely(
    response: httpx.Response,
    *,
    provider_code: str,
    request_url: str,
    secrets: tuple[str, ...] = (),
) -> None:
    if 200 <= response.status_code < 300:
        return
    safe_request = httpx.Request(response.request.method, _strip_url_query(request_url))
    safe_response = httpx.Response(
        response.status_code,
        headers=_redact_sensitive_data(dict(response.headers), secrets=secrets),
        content=_redact_sensitive_data(response.content, secrets=secrets),
        request=safe_request,
    )
    raise httpx.HTTPStatusError(
        f"{provider_code} request failed with HTTP {response.status_code}",
        request=safe_request,
        response=safe_response,
    )


def _sanitized_transport_error(*, provider_code: str, request_url: str) -> httpx.TransportError:
    return httpx.TransportError(
        f"{provider_code} transport request failed",
        request=httpx.Request("GET", _strip_url_query(request_url)),
    )


class ProviderAdapter(ABC):
    code: str

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client

    async def probe(
        self,
        provider: Provider,
        source: SourceSeries,
        dataset: Dataset,
    ) -> MappingProbeResult:
        """Collect read-only mapping evidence when the provider supports probing."""

        raise NotImplementedError(f"MappingProbe is not implemented for {self.code}")

    @abstractmethod
    async def fetch(
        self,
        provider: Provider,
        mappings: list[tuple[SourceSeries, Dataset]],
        *,
        mode: str,
    ) -> list[ProviderFetchResult]:
        raise NotImplementedError


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in {".", "NA", "N/A", "(NA)", "null", "None", "--"}:
        return None
    try:
        return Decimal(text)
    except Exception:
        return None


def period_end(period_start: date, frequency: str) -> date:
    normalized = frequency.lower().replace("_", "-")
    if normalized == "daily":
        return period_start
    if normalized == "weekly":
        return period_start + timedelta(days=6)
    if normalized == "monthly":
        last = calendar.monthrange(period_start.year, period_start.month)[1]
        return period_start.replace(day=last)
    if normalized == "quarterly":
        month = period_start.month + 2
        last = calendar.monthrange(period_start.year, month)[1]
        return date(period_start.year, month, last)
    if normalized in {"semiannual", "semi-annual"}:
        month = 6 if period_start.month == 1 else 12
        last = calendar.monthrange(period_start.year, month)[1]
        return date(period_start.year, month, last)
    if normalized == "annual":
        return date(period_start.year, 12, 31)
    return period_start


def parse_period_code(year: int, period_code: str, frequency: str) -> date | None:
    """Parse BLS-style period codes without silently treating quarterly data as monthly."""

    code = period_code.strip().upper()
    normalized = frequency.lower().replace("_", "-")
    if code.startswith("M") and code[1:].isdigit():
        month = int(code[1:])
        if 1 <= month <= 12:
            return date(year, month, 1)
        if month == 13 and normalized == "annual":
            return date(year, 1, 1)
        return None
    if code.startswith("Q"):
        digits = re.sub(r"\D", "", code)
        quarter = int(digits) if digits else 0
        if 1 <= quarter <= 4:
            return date(year, (quarter - 1) * 3 + 1, 1)
        return None
    if code.startswith("S") or code.startswith("H"):
        digits = re.sub(r"\D", "", code)
        half = int(digits) if digits else 0
        if 1 <= half <= 2:
            return date(year, 1 if half == 1 else 7, 1)
        return None
    if code.startswith("A") and normalized == "annual":
        return date(year, 1, 1)
    return None


def normalize_label(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value.lower()).split())


def deduplicate_observations(
    observations: Iterable[NormalizedObservation],
) -> list[NormalizedObservation]:
    """Remove exact duplicate rows and reject contradictory rows in one source snapshot."""

    seen: dict[tuple[int, date, datetime], NormalizedObservation] = {}
    for item in observations:
        if item.period_end < item.period_start:
            raise ProviderDataError(
                f"Invalid period for source_series_id={item.source_series_id}: "
                f"{item.period_start}..{item.period_end}"
            )
        key = (item.source_series_id, item.period_start, item.vintage_at)
        previous = seen.get(key)
        if previous is None:
            seen[key] = item
            continue
        comparable_previous = (
            previous.period_end,
            previous.value,
            previous.value_text,
            previous.status,
            previous.published_at,
        )
        comparable_current = (
            item.period_end,
            item.value,
            item.value_text,
            item.status,
            item.published_at,
        )
        if comparable_previous != comparable_current:
            raise ProviderDataError(
                "Conflicting duplicate upstream rows for "
                f"source_series_id={item.source_series_id}, period={item.period_start}, "
                f"vintage={item.vintage_at.isoformat()}"
            )
    return sorted(
        seen.values(),
        key=lambda item: (item.source_series_id, item.period_start, item.vintage_at),
    )


def apply_mapping_transform(
    observations: list[NormalizedObservation], source: SourceSeries
) -> list[NormalizedObservation]:
    transformed = observations
    transform = source.source_locator.get("transform")
    if transform == "period_difference":
        periods = int(source.source_locator.get("periods", 1))
        ordered = sorted(observations, key=lambda item: item.period_start)
        result: list[NormalizedObservation] = []
        for index, item in enumerate(ordered):
            value: Decimal | None = None
            flags = list(item.quality_flags)
            if index >= periods:
                previous = ordered[index - periods]
                expected_previous = _shift_period(
                    item.period_start, source.source_frequency or "monthly", -periods
                )
                if previous.period_start != expected_previous:
                    flags.append("derived_missing_predecessor")
                elif item.value is not None and previous.value is not None:
                    value = item.value - previous.value
            result.append(
                NormalizedObservation(
                    source_series_id=item.source_series_id,
                    period_start=item.period_start,
                    period_end=item.period_end,
                    value=value,
                    status=item.status,
                    published_at=item.published_at,
                    vintage_at=item.vintage_at,
                    source_updated_at=item.source_updated_at,
                    quality_flags=flags + ["derived_period_difference"],
                )
            )
        transformed = result
    elif transform not in {None, "", "identity"}:
        raise ProviderDataError(f"Unsupported source mapping transform: {transform!r}")

    scale_raw = source.source_locator.get("scale_factor")
    if scale_raw is None:
        return transformed
    try:
        scale = Decimal(str(scale_raw))
    except Exception as exc:
        raise ProviderDataError(f"Invalid source scale_factor={scale_raw!r}") from exc
    if scale == 0:
        raise ProviderDataError("source scale_factor cannot be zero")
    scaled: list[NormalizedObservation] = []
    for item in transformed:
        scaled.append(
            NormalizedObservation(
                source_series_id=item.source_series_id,
                period_start=item.period_start,
                period_end=item.period_end,
                value=item.value * scale if item.value is not None else None,
                value_text=item.value_text,
                status=item.status,
                published_at=item.published_at,
                vintage_at=item.vintage_at,
                source_updated_at=item.source_updated_at,
                quality_flags=[*item.quality_flags, f"scaled_by:{scale}"],
            )
        )
    return scaled


def _shift_period(value: date, frequency: str, periods: int) -> date:
    normalized = frequency.lower().replace("_", "-")
    if normalized == "monthly":
        month_index = value.year * 12 + value.month - 1 + periods
        return date(month_index // 12, month_index % 12 + 1, 1)
    if normalized == "quarterly":
        month_index = value.year * 12 + value.month - 1 + periods * 3
        return date(month_index // 12, month_index % 12 + 1, 1)
    if normalized in {"semiannual", "semi-annual"}:
        month_index = value.year * 12 + value.month - 1 + periods * 6
        return date(month_index // 12, month_index % 12 + 1, 1)
    if normalized == "annual":
        return date(value.year + periods, 1, 1)
    if normalized == "weekly":
        return value + timedelta(days=periods * 7)
    return value + timedelta(days=periods)
