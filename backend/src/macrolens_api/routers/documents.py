from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..dependencies import CurrentUser, SessionDep
from ..errors import AppError
from ..models import Document, DocumentVersion, Provider
from ..schemas import DocumentDetail
from ..services.documents import get_document, list_documents
from ..services.jobs import enqueue_job
from ..services.licenses import get_license_for_provider

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.get("")
async def documents(
    session: SessionDep,
    q: str | None = Query(default=None, max_length=300),
    document_type: str | None = None,
    provider: str | None = None,
    series_id: UUID | None = None,
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    items, total = await list_documents(
        session,
        q=q,
        document_type=document_type,
        provider_code=provider,
        series_id=series_id,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [item.model_dump(mode="json") for item in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/{document_id}", response_model=DocumentDetail)
async def document_detail(document_id: UUID, session: SessionDep) -> DocumentDetail:
    return await get_document(session, document_id, include_content=False)


@router.get("/{document_id}/content", response_model=DocumentDetail)
async def document_content(document_id: UUID, session: SessionDep) -> DocumentDetail:
    return await get_document(session, document_id, include_content=True)


@router.post("/{document_id}/summary", status_code=202)
async def generate_document_summary(
    document_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
) -> dict[str, str]:
    document_row = (
        await session.execute(
            select(Document, Provider)
            .join(Provider, Provider.id == Document.provider_id)
            .where(Document.id == document_id)
        )
    ).first()
    if document_row is None:
        raise AppError(404, "文档不存在", "没有找到该文档。", "document_not_found")
    document, provider = document_row
    license_info = await get_license_for_provider(session, provider.id)
    if not license_info.ai_context_allowed:
        raise AppError(
            403, "文档许可限制", "该文档来源不允许进入 AI 上下文。", "license_ai_context_denied"
        )
    version = await session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.version_no.desc())
        .limit(1)
    )
    if version is None:
        raise AppError(409, "文档尚未解析", "请先完成文档解析任务。", "document_not_parsed")
    job = await enqueue_job(
        session,
        job_type="summarize_document",
        payload={"document_version_id": str(version.id)},
        idempotency_key=f"summarize-document:{version.id}",
        priority=7,
        max_attempts=3,
    )
    return {"status": "queued", "job_id": str(job.id)}
