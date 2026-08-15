from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AppError
from ..models import (
    AIContext,
    Document,
    DocumentChunk,
    DocumentVersion,
    FomcMeeting,
    Note,
    Project,
    ReleaseEvent,
    SavedView,
)
from .data_browser import _license_map, _load_candidates, _points_by_source, normalize_data_as_of
from .licenses import get_strict_license_for_provider


async def _document_chunks(
    session: AsyncSession,
    *,
    version_id: UUID,
    query: str | None,
    limit: int = 8,
) -> list[DocumentChunk]:
    base = select(DocumentChunk).where(DocumentChunk.document_version_id == version_id)
    if query and query.strip():
        ts_query = func.websearch_to_tsquery("simple", query.strip())
        vector = func.to_tsvector("simple", DocumentChunk.content)
        ranked = list(
            (
                await session.scalars(
                    base.where(vector.op("@@")(ts_query))
                    .order_by(func.ts_rank_cd(vector, ts_query).desc(), DocumentChunk.chunk_no)
                    .limit(limit)
                )
            ).all()
        )
        if ranked:
            return ranked
    return list((await session.scalars(base.order_by(DocumentChunk.chunk_no).limit(limit))).all())


async def snapshot_context(
    session: AsyncSession,
    context_type: str,
    context_id: UUID,
    *,
    query: str | None = None,
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    data_as_of: datetime | None = None,
    historical_cutoff: bool = False,
) -> dict[str, Any]:
    if context_type == "series":
        if workspace_id is None or user_id is None:
            raise AppError(
                403,
                "上下文权限不足",
                "指标 AI 上下文需要用户工作区范围。",
                "context_scope_required",
            )
        candidates = await _load_candidates(session, series_id=context_id)
        if not candidates:
            raise AppError(
                404,
                "指标不存在",
                "AI 上下文中的指标不存在。",
                "context_series_not_found",
            )
        candidate = candidates[0]
        if candidate.binding is None:
            code = (
                "source_mapping_not_ready"
                if candidate.source_status == "missing"
                else "source_mapping_conflict"
            )
            raise AppError(
                409,
                "指标数据源不可用",
                "指标必须且只能有一个已验证主数据源，才能进入 AI 上下文。",
                code,
            )
        binding = candidate.binding
        license_info = (await _license_map(session, [binding]))[binding.source.id]
        # Capabilities are only a UI hint. Re-evaluate both display and AI permissions in the
        # mutating request, before persisting any snapshot.
        if not license_info.display_allowed or not license_info.ai_context_allowed:
            raise AppError(
                403,
                "数据许可限制",
                "该数据源不允许用于 AI 上下文。",
                "ai_license_forbidden",
            )
        cutoff = normalize_data_as_of(data_as_of)
        recent = (
            await _points_by_source(
                session,
                {binding.source.id},
                data_as_of=cutoff,
                max_points=36,
            )
        ).get(binding.source.id, [])
        if not recent:
            raise AppError(
                409,
                "快照不可用",
                "指定 data_as_of 无法复现该指标的观测。",
                "snapshot_unavailable",
                {"data_as_of": cutoff.isoformat()},
            )
        series = candidate.series
        return {
            "type": "series",
            "id": str(series.id),
            "name": series.name_zh,
            "canonical_code": series.canonical_code,
            "data_as_of": cutoff.isoformat(),
            "transform": series.default_transform,
            "unit": series.unit_label_zh,
            "observations": [
                {
                    "period_start": point.period_start.isoformat(),
                    "period_end": point.period_end.isoformat(),
                    "value": str(point.value) if point.value is not None else None,
                    "value_text": point.value_text,
                    "status": point.status,
                    "published_at": (
                        point.published_at.isoformat()
                        if isinstance(point.published_at, datetime)
                        else None
                    ),
                    "vintage_at": (
                        point.vintage_at.isoformat()
                        if isinstance(point.vintage_at, datetime)
                        else None
                    ),
                }
                for point in recent
            ],
            "lineage": {
                "provider": binding.provider.code,
                "dataset": binding.dataset.code,
                "provider_series_id": binding.source.provider_series_id,
                "source_series_id": binding.source.id,
                "source_locator": binding.source.source_locator,
            },
            "license": license_info.model_dump(mode="json"),
            "workspace_id": str(workspace_id),
        }
    if historical_cutoff:
        cutoff = normalize_data_as_of(data_as_of)
        raise AppError(
            409,
            "历史上下文不可复现",
            f"{context_type} 上下文没有可证明的历史版本边界，不能加入历史 AI 快照。",
            "historical_context_unavailable",
            {"context_type": context_type, "data_as_of": cutoff.isoformat()},
        )
    if context_type == "document":
        document = await session.get(Document, context_id)
        if document is None:
            raise AppError(
                404,
                "文档不存在",
                "AI 上下文中的文档不存在。",
                "context_document_not_found",
            )
        license_info = await get_strict_license_for_provider(session, document.provider_id)
        if not license_info.ai_context_allowed:
            raise AppError(
                403,
                "文档许可限制",
                "该文档来源不允许用于 AI 上下文。",
                "ai_license_forbidden",
            )
        version = await session.scalar(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document.id)
            .order_by(DocumentVersion.version_no.desc())
            .limit(1)
        )
        chunks: list[dict[str, Any]] = []
        if version:
            rows = await _document_chunks(session, version_id=version.id, query=query, limit=8)
            chunks = [
                {
                    "chunk_id": str(chunk.id),
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "heading": chunk.heading_path,
                    "content": chunk.content[:2500],
                }
                for chunk in rows
            ]
        return {
            "type": "document",
            "id": str(document.id),
            "title": document.title_zh or document.title,
            "source_url": document.source_url,
            "published_at": document.published_at.isoformat() if document.published_at else None,
            "version_id": str(version.id) if version else None,
            "summary": version.ai_summary_zh if version else None,
            "chunks": chunks,
            "license": license_info.model_dump(mode="json"),
        }
    if context_type == "release_event":
        event = await session.get(ReleaseEvent, context_id)
        if event is None:
            raise AppError(
                404, "发布事件不存在", "AI 上下文中的事件不存在。", "context_event_not_found"
            )
        return {
            "type": "release_event",
            "id": str(event.id),
            "title": event.title_zh,
            "scheduled_at": event.scheduled_at.isoformat(),
            "status": event.status,
            "reference_period": event.reference_period,
            "official_url": event.official_url,
        }
    if context_type == "fomc_meeting":
        meeting = await session.get(FomcMeeting, context_id)
        if meeting is None:
            raise AppError(
                404, "FOMC会议不存在", "AI 上下文中的会议不存在。", "context_fomc_not_found"
            )
        return {
            "type": "fomc_meeting",
            "id": str(meeting.id),
            "meeting_start": meeting.meeting_start.isoformat(),
            "meeting_end": meeting.meeting_end.isoformat(),
            "decision_code": meeting.decision_code,
            "target_rate_lower": str(meeting.target_rate_lower)
            if meeting.target_rate_lower is not None
            else None,
            "target_rate_upper": str(meeting.target_rate_upper)
            if meeting.target_rate_upper is not None
            else None,
            "summary": meeting.summary_zh,
            "official_url": meeting.official_url,
        }
    if context_type == "saved_view":
        if workspace_id is None or user_id is None:
            raise AppError(
                403, "上下文权限不足", "保存视图需要用户工作区上下文。", "context_scope_required"
            )
        view = await session.scalar(
            select(SavedView).where(
                SavedView.id == context_id,
                SavedView.workspace_id == workspace_id,
                SavedView.owner_user_id == user_id,
            )
        )
        if view is None:
            raise AppError(
                404,
                "保存视图不存在",
                "AI 上下文中的保存视图不存在。",
                "context_saved_view_not_found",
            )
        return {
            "type": "saved_view",
            "id": str(view.id),
            "name": view.name,
            "view_type": view.view_type,
            "description": view.description,
            "definition": view.definition,
            "updated_at": view.updated_at.isoformat(),
        }
    if context_type == "note":
        if workspace_id is None or user_id is None:
            raise AppError(
                403, "上下文权限不足", "研究笔记需要用户工作区上下文。", "context_scope_required"
            )
        note = await session.scalar(
            select(Note)
            .outerjoin(Project, Project.id == Note.project_id)
            .where(
                Note.id == context_id,
                Note.author_user_id == user_id,
                ((Project.workspace_id == workspace_id) | (Note.project_id.is_(None))),
            )
        )
        if note is None:
            raise AppError(
                404, "研究笔记不存在", "AI 上下文中的研究笔记不存在。", "context_note_not_found"
            )
        return {
            "type": "note",
            "id": str(note.id),
            "title": note.title,
            "body_markdown": note.body_markdown,
            "version_no": note.version_no,
            "updated_at": note.updated_at.isoformat(),
        }
    raise AppError(
        422, "上下文类型不支持", f"暂不支持 {context_type} 上下文。", "unsupported_context"
    )


async def persist_contexts(
    session: AsyncSession,
    *,
    ai_run_id: UUID,
    contexts: list[tuple[str, UUID]],
    query: str | None = None,
    workspace_id: UUID | None = None,
    user_id: UUID | None = None,
    data_as_of: datetime | None = None,
    historical_cutoff: bool = False,
) -> None:
    total_chars = 0
    for context_type, context_id in contexts:
        snapshot = await snapshot_context(
            session,
            context_type,
            context_id,
            query=query,
            workspace_id=workspace_id,
            user_id=user_id,
            data_as_of=data_as_of,
            historical_cutoff=historical_cutoff,
        )
        total_chars += len(json.dumps(snapshot, ensure_ascii=False, default=str))
        if total_chars > 180_000:
            raise AppError(
                422,
                "AI上下文过大",
                "请选择更少的文档或指标，当前上下文超过安全处理上限。",
                "ai_context_too_large",
            )
        session.add(
            AIContext(
                ai_run_id=ai_run_id,
                context_type=context_type,
                context_id=context_id,
                snapshot=snapshot,
            )
        )
    await session.flush()


def data_as_of_from_snapshots(snapshots: list[dict[str, Any]]) -> datetime:
    candidates: list[datetime] = []
    for snapshot in snapshots:
        value = (
            snapshot.get("data_as_of")
            or snapshot.get("published_at")
            or snapshot.get("scheduled_at")
        )
        if value:
            try:
                candidate = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError:
                continue
            if candidate.tzinfo is None:
                candidate = candidate.replace(tzinfo=UTC)
            else:
                candidate = candidate.astimezone(UTC)
            candidates.append(candidate)
    return max(candidates, default=datetime.now(UTC))
