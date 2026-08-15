from __future__ import annotations

import hashlib
import json

from ..models import Dataset, Provider, SourceSeries


def source_mapping_fingerprint(
    source: SourceSeries,
    dataset: Dataset,
    provider: Provider,
) -> str:
    """Hash every mapping field that can affect identity or parsing approval."""

    payload = {
        "provider_code": provider.code,
        "dataset_id": dataset.id,
        "dataset_code": dataset.code,
        "source_series_id": source.id,
        "provider_series_id": source.provider_series_id,
        "source_locator": source.source_locator,
        "mapping_type": source.mapping_type,
        "source_frequency": source.source_frequency,
        "source_unit": source.source_unit,
        "source_seasonal_adjustment": source.source_seasonal_adjustment,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()
