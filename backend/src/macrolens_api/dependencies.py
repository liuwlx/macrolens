from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .errors import AppError
from .models import RefreshSession, User, Workspace
from .security import TokenType, decode_token

SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def get_current_user(
    session: SessionDep,
    macrolens_access: Annotated[str | None, Cookie()] = None,
) -> User:
    if not macrolens_access:
        raise AppError(401, "需要登录", "请先登录后再继续。", "authentication_required")
    token = decode_token(macrolens_access, TokenType.ACCESS)
    auth_session = await session.get(RefreshSession, token.sid)
    if auth_session is None or auth_session.user_id != token.sub or auth_session.revoked_at is not None:
        raise AppError(401, "登录会话已失效", "请重新登录。", "session_revoked")
    user = await session.get(User, token.sub)
    if user is None or not user.active:
        raise AppError(401, "用户不可用", "当前用户不存在或已被停用。", "inactive_user")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_workspace(session: SessionDep, user: CurrentUser) -> Workspace:
    workspace = await session.scalar(
        select(Workspace).where(Workspace.owner_user_id == user.id).order_by(Workspace.created_at)
    )
    if workspace is None:
        workspace = Workspace(name=f"{user.display_name}的工作区", owner_user_id=user.id)
        session.add(workspace)
        await session.commit()
        await session.refresh(workspace)
    return workspace


CurrentWorkspace = Annotated[Workspace, Depends(get_current_workspace)]


def require_admin(user: CurrentUser) -> User:
    if user.role != "admin":
        raise AppError(403, "权限不足", "该操作仅限管理员。", "admin_required")
    return user


AdminUser = Annotated[User, Depends(require_admin)]


def assert_workspace_owner(workspace_id: UUID, workspace: Workspace) -> None:
    if workspace_id != workspace.id:
        raise AppError(403, "无权访问", "该资源不属于当前工作区。", "workspace_forbidden")
