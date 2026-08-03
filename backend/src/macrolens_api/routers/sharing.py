from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Response
from sqlalchemy import select

from ..config import get_settings
from ..dependencies import CurrentUser, CurrentWorkspace, SessionDep
from ..errors import AppError
from ..models import Note, Project, ProjectItem, ProjectShareLink
from ..schemas import NotePublic, ProjectDetail, ProjectItemPublic, ProjectPublic, ProjectShareCreate, ProjectSharePublic

settings = get_settings()
private_router = APIRouter(prefix="/me/projects", tags=["Project sharing"])
public_router = APIRouter(prefix="/shared/projects", tags=["Project sharing"])


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _owned_project(project_id: UUID, session: SessionDep, user: CurrentUser, workspace: CurrentWorkspace) -> Project:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace.id,
            Project.owner_user_id == user.id,
        )
    )
    if project is None:
        raise AppError(404, "研究项目不存在", "没有找到可共享的项目。", "project_not_found")
    return project


@private_router.post("/{project_id}/shares", response_model=ProjectSharePublic, status_code=201)
async def create_share(
    project_id: UUID,
    payload: ProjectShareCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> ProjectSharePublic:
    await _owned_project(project_id, session, user, workspace)
    token = secrets.token_urlsafe(32)
    row = ProjectShareLink(
        project_id=project_id,
        created_by_user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=datetime.now(UTC) + timedelta(days=payload.expires_in_days),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return ProjectSharePublic(
        id=row.id,
        project_id=row.project_id,
        share_url=f"{settings.web_origin}/shared/project/{token}",
        expires_at=row.expires_at,
        revoked_at=row.revoked_at,
        created_at=row.created_at,
    )


@private_router.get("/{project_id}/shares", response_model=list[ProjectSharePublic])
async def list_shares(
    project_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> list[ProjectSharePublic]:
    await _owned_project(project_id, session, user, workspace)
    rows = list(
        (
            await session.scalars(
                select(ProjectShareLink)
                .where(ProjectShareLink.project_id == project_id)
                .order_by(ProjectShareLink.created_at.desc())
            )
        ).all()
    )
    return [
        ProjectSharePublic(
            id=row.id,
            project_id=row.project_id,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
            created_at=row.created_at,
        )
        for row in rows
    ]


@private_router.delete("/{project_id}/shares/{share_id}", status_code=204)
async def revoke_share(
    project_id: UUID,
    share_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    await _owned_project(project_id, session, user, workspace)
    row = await session.scalar(
        select(ProjectShareLink).where(ProjectShareLink.id == share_id, ProjectShareLink.project_id == project_id)
    )
    if row is None:
        raise AppError(404, "分享链接不存在", "没有找到该分享链接。", "share_not_found")
    row.revoked_at = datetime.now(UTC)
    await session.commit()
    return Response(status_code=204)


@public_router.get("/{token}", response_model=ProjectDetail)
async def shared_project(token: str, session: SessionDep) -> ProjectDetail:
    now = datetime.now(UTC)
    share = await session.scalar(
        select(ProjectShareLink).where(
            ProjectShareLink.token_hash == _hash_token(token),
            ProjectShareLink.revoked_at.is_(None),
            ProjectShareLink.expires_at > now,
        )
    )
    if share is None:
        raise AppError(404, "分享链接不可用", "链接不存在、已撤销或已过期。", "share_invalid")
    project = await session.get(Project, share.project_id)
    if project is None:
        raise AppError(404, "研究项目不存在", "分享的项目已被删除。", "project_not_found")
    items = list(
        (
            await session.scalars(
                select(ProjectItem)
                .where(ProjectItem.project_id == project.id)
                .order_by(ProjectItem.sort_order, ProjectItem.created_at)
            )
        ).all()
    )
    notes = list(
        (
            await session.scalars(
                select(Note).where(Note.project_id == project.id).order_by(Note.updated_at.desc())
            )
        ).all()
    )
    return ProjectDetail(
        **ProjectPublic.model_validate(project).model_dump(),
        items=[ProjectItemPublic.model_validate(item) for item in items],
        notes=[NotePublic.model_validate(note) for note in notes],
    )
