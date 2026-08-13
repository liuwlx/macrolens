from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from macrolens_api.models import Dataset, Provider, RawObject, SourceSeries
from macrolens_api.services.source_mapping_identity import source_mapping_fingerprint
from macrolens_api.services.storage import ObjectStorage
from macrolens_worker.providers.bls import BLSAdapter


async def probe_mapping(
    session: AsyncSession,
    *,
    source_series_id: int,
) -> dict[str, Any]:
    """Run one read-only MappingProbe through the production Worker adapter."""

    row = (
        await session.execute(
            select(SourceSeries, Dataset, Provider)
            .join(Dataset, Dataset.id == SourceSeries.dataset_id)
            .join(Provider, Provider.id == Dataset.provider_id)
            .where(
                SourceSeries.id == source_series_id,
                Dataset.active.is_(True),
                Provider.active.is_(True),
            )
        )
    ).one_or_none()
    if row is None:
        raise RuntimeError(f"Unknown or inactive source mapping: {source_series_id}")
    source, dataset, provider = row
    if provider.code != BLSAdapter.code:
        raise RuntimeError(
            f"MappingProbe is not implemented for provider {provider.code}"
        )
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(30, connect=20),
        follow_redirects=True,
        headers={"User-Agent": "MacroLens/1.0 mapping-probe"},
    ) as client:
        evidence = await BLSAdapter(client).probe(provider, source, dataset)
    result = asdict(evidence)
    result["probed_at"] = evidence.probed_at.isoformat()
    result["mapping_fingerprint"] = source_mapping_fingerprint(source, dataset, provider)
    return result


async def replay_bls_raw(
    session: AsyncSession,
    *,
    raw_object_id: UUID,
    source_series_ids: list[int],
) -> dict[str, Any]:
    """Replay one immutable BLS raw object without external network access or writes."""

    raw_object = await session.get(RawObject, raw_object_id)
    if raw_object is None:
        raise RuntimeError(f"Unknown raw object: {raw_object_id}")
    requested_ids = set(source_series_ids)
    if not requested_ids or len(requested_ids) != len(source_series_ids):
        raise RuntimeError("source_series_ids must contain unique IDs")
    rows = (
        await session.execute(
            select(SourceSeries, Dataset, Provider)
            .join(Dataset, Dataset.id == SourceSeries.dataset_id)
            .join(Provider, Provider.id == Dataset.provider_id)
            .where(
                SourceSeries.id.in_(requested_ids),
                Provider.id == raw_object.provider_id,
                Dataset.id == raw_object.dataset_id,
            )
            .order_by(SourceSeries.id)
        )
    ).all()
    mappings = [(row[0], row[1]) for row in rows]
    if {source.id for source, _dataset in mappings} != requested_ids:
        raise RuntimeError("Replay scope does not match the raw object's provider mappings")
    provider = rows[0][2]
    if provider.code != BLSAdapter.code:
        raise RuntimeError("Raw replay is only implemented for BLS_API_V2")
    storage = ObjectStorage()
    prefix = f"s3://{storage.settings.s3_bucket}/"
    if not raw_object.object_uri.startswith(prefix):
        raise RuntimeError("Raw object URI is outside the configured immutable bucket")
    raw_bytes = await storage.get_bytes(raw_object.object_uri.removeprefix(prefix))
    if sha256(raw_bytes).hexdigest() != raw_object.sha256:
        raise RuntimeError("Raw object checksum mismatch")
    replayed = BLSAdapter.replay(
        provider,
        mappings,
        raw_bytes,
        vintage_at=raw_object.fetched_at,
    )
    periods = [item.period_start for item in replayed.observations]
    return {
        "status": "validated",
        "raw_object_id": str(raw_object.id),
        "raw_sha256": raw_object.sha256,
        "source_series_ids": sorted(requested_ids),
        "observation_count": len(replayed.observations),
        "first_period": min(periods).isoformat() if periods else None,
        "last_period": max(periods).isoformat() if periods else None,
        "network_requests": 0,
    }
