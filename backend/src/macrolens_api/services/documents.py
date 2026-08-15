from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy import Text, and_, cast, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AppError
from ..models import (
    Document,
    DocumentChunk,
    DocumentSeries,
    DocumentVersion,
    LicensePolicy,
    Provider,
    Series,
)
from ..schemas import (
    DocumentChunkPublic,
    DocumentDetail,
    DocumentSummary,
    SeriesSummary,
)
from .licenses import get_license_for_provider


async def _related_series(session: AsyncSession, document_id: UUID) -> list[SeriesSummary]:
    rows = (
        await session.execute(
            select(Series)
            .join(DocumentSeries, DocumentSeries.series_id == Series.id)
            .where(DocumentSeries.document_id == document_id)
            .order_by(Series.name_zh)
        )
    ).scalars()
    return [
        SeriesSummary(
            id=series.id,
            canonical_code=series.canonical_code,
            name_zh=series.name_zh,
            name_en=series.name_en,
            theme=series.theme,
            frequency=series.frequency,
            unit_code=series.unit_code,
            unit_label_zh=series.unit_label_zh,
            default_transform=series.default_transform,
            latest_period=series.latest_period,
        )
        for series in rows
    ]


async def list_documents(
    session: AsyncSession,
    *,
    q: str | None,
    document_type: str | None,
    provider_code: str | None,
    series_id: UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[DocumentSummary], int]:
    stmt = select(Document, Provider).join(Provider, Provider.id == Document.provider_id)
    today = date.today()
    active_policy = exists(
        select(LicensePolicy.id).where(
            LicensePolicy.provider_id == Provider.id,
            LicensePolicy.dataset_id.is_(None),
            or_(LicensePolicy.effective_from.is_(None), LicensePolicy.effective_from <= today),
            or_(LicensePolicy.effective_to.is_(None), LicensePolicy.effective_to >= today),
        )
    )
    display_policy = exists(
        select(LicensePolicy.id).where(
            LicensePolicy.provider_id == Provider.id,
            LicensePolicy.dataset_id.is_(None),
            LicensePolicy.display_allowed.is_(True),
            or_(LicensePolicy.effective_from.is_(None), LicensePolicy.effective_from <= today),
            or_(LicensePolicy.effective_to.is_(None), LicensePolicy.effective_to >= today),
        )
    )
    filters = [
        Document.status == "active",
        or_(display_policy, and_(~active_policy, Provider.redistribution_ok.is_(True))),
    ]
    if q:
        pattern = f"%{q.strip()}%"
        ts_query = func.websearch_to_tsquery("simple", q.strip())
        content_match = exists(
            select(DocumentVersion.id).where(
                DocumentVersion.document_id == Document.id,
                func.to_tsvector("simple", func.coalesce(DocumentVersion.extracted_text, "")).op(
                    "@@"
                )(ts_query),
            )
        )
        filters.append(
            or_(
                Document.title.ilike(pattern),
                Document.title_zh.ilike(pattern),
                cast(Document.metadata_json, Text).ilike(pattern),
                content_match,
            )
        )
    if document_type:
        filters.append(Document.document_type == document_type)
    if provider_code:
        filters.append(Provider.code == provider_code)
    if series_id:
        stmt = stmt.join(DocumentSeries, DocumentSeries.document_id == Document.id)
        filters.append(DocumentSeries.series_id == series_id)
    stmt = stmt.where(*filters)
    total = int(
        await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    )
    rows = (
        await session.execute(
            stmt.order_by(Document.published_at.desc().nullslast(), Document.title)
            .offset(offset)
            .limit(limit)
        )
    ).all()
    items: list[DocumentSummary] = []
    for document, provider in rows:
        latest_version = await session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_no.desc())
            .limit(1)
        )
        items.append(
            DocumentSummary(
                id=document.id,
                title=document.title,
                title_zh=document.title_zh,
                document_type=document.document_type,
                provider_code=provider.code,
                provider_name=provider.name,
                source_url=document.source_url,
                published_at=document.published_at,
                language=document.language,
                copyright_status=document.copyright_status,
                status=document.status,
                summary_zh=latest_version.ai_summary_zh if latest_version else None,
                related_series=await _related_series(session, document.id),
                license=await get_license_for_provider(session, provider.id),
            )
        )
    return items, total


async def get_document(
    session: AsyncSession, document_id: UUID, include_content: bool
) -> DocumentDetail:
    row = (
        await session.execute(
            select(Document, Provider)
            .join(Provider, Provider.id == Document.provider_id)
            .where(Document.id == document_id)
        )
    ).first()
    if row is None:
        raise AppError(404, "文档不存在", "没有找到该文档。", "document_not_found")
    document, provider = row
    license_info = await get_license_for_provider(session, provider.id)
    if not license_info.display_allowed:
        raise AppError(
            403, "文档许可限制", "该文档来源当前不允许在产品中展示。", "license_display_denied"
        )
    version = await session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_no.desc())
        .limit(1)
    )
    chunks: list[DocumentChunkPublic] = []
    if include_content and version is not None:
        chunk_rows = list(
            (
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_version_id == version.id)
                    .order_by(DocumentChunk.chunk_no)
                    .limit(500)
                )
            ).all()
        )
        chunks = [
            DocumentChunkPublic(
                id=chunk.id,
                chunk_no=chunk.chunk_no,
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                heading_path=chunk.heading_path,
                content=chunk.content,
            )
            for chunk in chunk_rows
        ]
    return DocumentDetail(
        id=document.id,
        title=document.title,
        title_zh=document.title_zh,
        document_type=document.document_type,
        provider_code=provider.code,
        provider_name=provider.name,
        source_url=document.source_url,
        published_at=document.published_at,
        language=document.language,
        copyright_status=document.copyright_status,
        status=document.status,
        summary_zh=version.ai_summary_zh if version else None,
        related_series=await _related_series(session, document.id),
        license=license_info,
        latest_version_id=version.id if version else None,
        version_no=version.version_no if version else None,
        content_hash=version.content_hash if version else None,
        extracted_text=version.extracted_text if include_content and version else None,
        translated_text_zh=version.translated_text_zh if include_content and version else None,
        chunks=chunks,
    )
