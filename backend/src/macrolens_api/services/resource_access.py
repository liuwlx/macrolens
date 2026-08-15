from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..errors import AppError
from ..models import AIRun, Document, FomcMeeting, Note, Project, ReleaseEvent, SavedView, Series


async def ensure_resource_access(
    session: AsyncSession,
    *,
    object_type: str,
    object_id: UUID,
    workspace_id: UUID,
    user_id: UUID,
) -> None:
    """Validate that a referenced resource exists and is visible to the caller.

    Public research resources only require existence. User-owned resources are scoped by both
    workspace and owner so arbitrary UUIDs cannot create cross-tenant favorites, project items,
    reports or AI associations.
    """

    public_models = {
        "series": Series,
        "document": Document,
        "release_event": ReleaseEvent,
        "fomc_meeting": FomcMeeting,
    }
    model = public_models.get(object_type)
    if model is not None:
        if await session.get(model, object_id) is None:
            raise AppError(404, "资源不存在", "没有找到所引用的资源。", f"{object_type}_not_found")
        return

    if object_type == "saved_view":
        found = await session.scalar(
            select(SavedView.id).where(
                SavedView.id == object_id,
                SavedView.workspace_id == workspace_id,
                SavedView.owner_user_id == user_id,
            )
        )
    elif object_type == "project":
        found = await session.scalar(
            select(Project.id).where(
                Project.id == object_id,
                Project.workspace_id == workspace_id,
                Project.owner_user_id == user_id,
            )
        )
    elif object_type == "ai_run":
        found = await session.scalar(
            select(AIRun.id).where(
                AIRun.id == object_id,
                AIRun.workspace_id == workspace_id,
                AIRun.user_id == user_id,
            )
        )
    elif object_type == "note":
        found = await session.scalar(
            select(Note.id)
            .outerjoin(Project, Project.id == Note.project_id)
            .where(
                Note.id == object_id,
                Note.author_user_id == user_id,
                (Note.project_id.is_(None) | (Project.workspace_id == workspace_id)),
            )
        )
    else:
        raise AppError(
            422, "资源类型不支持", f"暂不支持 {object_type} 资源。", "unsupported_resource_type"
        )

    if found is None:
        raise AppError(
            404,
            "资源不存在",
            "没有找到所引用的资源，或当前用户无权访问。",
            f"{object_type}_not_found",
        )
