from __future__ import annotations

from datetime import date

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import LicensePolicy, Provider, SourceSeries
from ..schemas import LicenseInfo


async def get_license_for_source(session: AsyncSession, source_series: SourceSeries) -> LicenseInfo | None:
    today = date.today()
    policy = await session.scalar(
        select(LicensePolicy)
        .where(
            LicensePolicy.provider_id == source_series.dataset.provider_id,
            or_(LicensePolicy.dataset_id == source_series.dataset_id, LicensePolicy.dataset_id.is_(None)),
            or_(LicensePolicy.effective_from.is_(None), LicensePolicy.effective_from <= today),
            or_(LicensePolicy.effective_to.is_(None), LicensePolicy.effective_to >= today),
        )
        .order_by(LicensePolicy.dataset_id.desc().nullslast(), LicensePolicy.created_at.desc())
    )
    if policy is None:
        provider = await session.get(Provider, source_series.dataset.provider_id)
        public = bool(provider and provider.redistribution_ok)
        return LicenseInfo(
            display_allowed=public,
            download_allowed=public,
            api_redistribution_allowed=public,
            ai_context_allowed=public,
            attribution_required=True,
            attribution_text=provider.attribution_text if provider else None,
        )
    return LicenseInfo(
        display_allowed=policy.display_allowed,
        download_allowed=policy.download_allowed,
        api_redistribution_allowed=policy.api_redistribution_allowed,
        ai_context_allowed=policy.ai_context_allowed,
        attribution_required=policy.attribution_required,
        attribution_text=policy.attribution_text,
    )


async def get_license_for_provider(
    session: AsyncSession, provider_id: int, dataset_id: int | None = None
) -> LicenseInfo:
    today = date.today()
    policy = await session.scalar(
        select(LicensePolicy)
        .where(
            LicensePolicy.provider_id == provider_id,
            or_(LicensePolicy.dataset_id == dataset_id, LicensePolicy.dataset_id.is_(None))
            if dataset_id is not None
            else LicensePolicy.dataset_id.is_(None),
            or_(LicensePolicy.effective_from.is_(None), LicensePolicy.effective_from <= today),
            or_(LicensePolicy.effective_to.is_(None), LicensePolicy.effective_to >= today),
        )
        .order_by(LicensePolicy.dataset_id.desc().nullslast(), LicensePolicy.created_at.desc())
    )
    provider = await session.get(Provider, provider_id)
    if provider is None:
        return LicenseInfo(
            display_allowed=False,
            download_allowed=False,
            api_redistribution_allowed=False,
            ai_context_allowed=False,
            attribution_required=True,
            attribution_text=None,
        )
    if policy is None:
        public = bool(provider.redistribution_ok)
        return LicenseInfo(
            display_allowed=public,
            download_allowed=public,
            api_redistribution_allowed=public,
            ai_context_allowed=public,
            attribution_required=True,
            attribution_text=provider.attribution_text,
        )
    return LicenseInfo(
        display_allowed=policy.display_allowed,
        download_allowed=policy.download_allowed,
        api_redistribution_allowed=policy.api_redistribution_allowed,
        ai_context_allowed=policy.ai_context_allowed,
        attribution_required=policy.attribution_required,
        attribution_text=policy.attribution_text,
    )
