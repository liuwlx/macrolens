from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Dataset, Job, Provider, SourceSeries
from .source_mapping_identity import source_mapping_fingerprint


async def approve_mapping_from_probe(
    session: AsyncSession,
    *,
    source_series_id: int,
    probe_job_id: UUID,
    verified_by: str,
) -> SourceSeries:
    """Atomically promote one probed mapping and demote every old primary."""

    probe_job = await session.scalar(
        select(Job).where(Job.id == probe_job_id).with_for_update()
    )
    if (
        probe_job is None
        or probe_job.job_type != "mapping_probe"
        or probe_job.status != "succeeded"
        or int(probe_job.payload.get("source_series_id", -1)) != source_series_id
    ):
        raise RuntimeError("A succeeded MappingProbe job for this source mapping is required")
    mapping_row = (
        await session.execute(
            select(SourceSeries, Dataset, Provider)
            .join(Dataset, Dataset.id == SourceSeries.dataset_id)
            .join(Provider, Provider.id == Dataset.provider_id)
            .where(SourceSeries.id == source_series_id)
            .with_for_update(of=SourceSeries)
        )
    ).one_or_none()
    if mapping_row is None:
        raise RuntimeError(f"Unknown source mapping: {source_series_id}")
    mapping, dataset, provider = mapping_row
    evidence = probe_job.result
    if (
        int(evidence.get("source_series_id", -1)) != source_series_id
        or evidence.get("provider_code") != provider.code
        or evidence.get("provider_series_id") != mapping.provider_series_id
        or evidence.get("http_reachable") is not True
        or not 200 <= int(evidence.get("http_status", 0)) < 300
        or not evidence.get("business_success")
        or not evidence.get("identity_match")
        or evidence.get("authorization_available") is not True
        or not evidence.get("production_ready")
        or evidence.get("classification") != "PASS"
        or re.fullmatch(r"[0-9a-f]{64}", str(evidence.get("response_sha256", "")))
        is None
        or evidence.get("mapping_fingerprint")
        != source_mapping_fingerprint(mapping, dataset, provider)
    ):
        raise RuntimeError("MappingProbe evidence is not approved for production")
    approval = evidence.get("approval")
    if isinstance(approval, dict):
        if (
            int(approval.get("source_series_id", -1)) == source_series_id
            and mapping.mapping_status == "verified"
            and mapping.is_primary
            and mapping.verification_job_id == probe_job.id
            and mapping.verification_fingerprint == evidence["mapping_fingerprint"]
        ):
            return mapping
        raise RuntimeError("MappingProbe evidence was already consumed inconsistently")
    approved_at = datetime.now(UTC)
    await session.execute(
        update(SourceSeries)
        .where(SourceSeries.series_id == mapping.series_id)
        .values(is_primary=False)
    )
    mapping.mapping_status = "verified"
    mapping.is_primary = True
    mapping.verified_by = verified_by
    mapping.verified_at = approved_at
    mapping.verification_job_id = probe_job.id
    mapping.verification_fingerprint = evidence["mapping_fingerprint"]
    probe_job.result = {
        **evidence,
        "approval": {
            "source_series_id": source_series_id,
            "verified_by": verified_by,
            "approved_at": approved_at.isoformat(),
        },
    }
    await session.commit()
    return mapping
