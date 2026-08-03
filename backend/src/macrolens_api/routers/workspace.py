from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response
from sqlalchemy import or_, select

from ..dependencies import CurrentUser, CurrentWorkspace, SessionDep
from ..errors import AppError
from ..models import AlertRule, Favorite, Note, Notification, Project, ProjectItem, SavedView
from ..services.resource_access import ensure_resource_access
from ..schemas import (
    AlertCreate,
    AlertPublic,
    FavoriteCreate,
    FavoritePublic,
    NoteCreate,
    NotePublic,
    NoteUpdate,
    NotificationPublic,
    ProjectCreate,
    ProjectDetail,
    ProjectItemCreate,
    ProjectItemPublic,
    ProjectPublic,
    SavedViewCreate,
    SavedViewPublic,
    SavedViewUpdate,
)

router = APIRouter(prefix="/me", tags=["Workspace"])


@router.get("/favorites", response_model=list[FavoritePublic])
async def favorites(session: SessionDep, user: CurrentUser, workspace: CurrentWorkspace) -> list[FavoritePublic]:
    rows = list(
        (
            await session.scalars(
                select(Favorite)
                .where(Favorite.workspace_id == workspace.id, Favorite.user_id == user.id)
                .order_by(Favorite.group_name.nullslast(), Favorite.sort_order, Favorite.created_at.desc())
            )
        ).all()
    )
    return [FavoritePublic.model_validate(row) for row in rows]


@router.post("/favorites", response_model=FavoritePublic, status_code=201)
async def create_favorite(
    payload: FavoriteCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> FavoritePublic:
    await ensure_resource_access(
        session,
        object_type=payload.object_type,
        object_id=payload.object_id,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    existing = await session.scalar(
        select(Favorite).where(
            Favorite.workspace_id == workspace.id,
            Favorite.user_id == user.id,
            Favorite.object_type == payload.object_type,
            Favorite.object_id == payload.object_id,
        )
    )
    if existing:
        return FavoritePublic.model_validate(existing)
    favorite = Favorite(
        workspace_id=workspace.id,
        user_id=user.id,
        object_type=payload.object_type,
        object_id=payload.object_id,
        group_name=payload.group_name,
        note=payload.note,
    )
    session.add(favorite)
    await session.commit()
    await session.refresh(favorite)
    return FavoritePublic.model_validate(favorite)


@router.delete("/favorites/{favorite_id}", status_code=204)
async def delete_favorite(
    favorite_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    favorite = await session.scalar(
        select(Favorite).where(
            Favorite.id == favorite_id,
            Favorite.workspace_id == workspace.id,
            Favorite.user_id == user.id,
        )
    )
    if favorite is None:
        raise AppError(404, "收藏不存在", "没有找到该收藏。", "favorite_not_found")
    await session.delete(favorite)
    await session.commit()
    return Response(status_code=204)


@router.get("/saved-views", response_model=list[SavedViewPublic])
async def saved_views(
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
    view_type: str | None = None,
) -> list[SavedViewPublic]:
    stmt = select(SavedView).where(
        SavedView.workspace_id == workspace.id,
        SavedView.owner_user_id == user.id,
    )
    if view_type:
        stmt = stmt.where(SavedView.view_type == view_type)
    rows = list((await session.scalars(stmt.order_by(SavedView.updated_at.desc()))).all())
    return [SavedViewPublic.model_validate(row) for row in rows]


@router.post("/saved-views", response_model=SavedViewPublic, status_code=201)
async def create_saved_view(
    payload: SavedViewCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> SavedViewPublic:
    view = SavedView(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        name=payload.name,
        view_type=payload.view_type,
        definition=payload.definition,
        description=payload.description,
    )
    session.add(view)
    await session.commit()
    await session.refresh(view)
    return SavedViewPublic.model_validate(view)


@router.get("/saved-views/{view_id}", response_model=SavedViewPublic)
async def get_saved_view(
    view_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> SavedViewPublic:
    view = await session.scalar(
        select(SavedView).where(
            SavedView.id == view_id,
            SavedView.workspace_id == workspace.id,
            SavedView.owner_user_id == user.id,
        )
    )
    if view is None:
        raise AppError(404, "保存视图不存在", "没有找到该保存视图。", "saved_view_not_found")
    return SavedViewPublic.model_validate(view)


@router.patch("/saved-views/{view_id}", response_model=SavedViewPublic)
async def update_saved_view(
    view_id: UUID,
    payload: SavedViewUpdate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> SavedViewPublic:
    view = await session.scalar(
        select(SavedView).where(
            SavedView.id == view_id,
            SavedView.workspace_id == workspace.id,
            SavedView.owner_user_id == user.id,
        )
    )
    if view is None:
        raise AppError(404, "保存视图不存在", "没有找到该保存视图。", "saved_view_not_found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(view, key, value)
    await session.commit()
    await session.refresh(view)
    return SavedViewPublic.model_validate(view)


@router.delete("/saved-views/{view_id}", status_code=204)
async def delete_saved_view(
    view_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    view = await session.scalar(
        select(SavedView).where(
            SavedView.id == view_id,
            SavedView.workspace_id == workspace.id,
            SavedView.owner_user_id == user.id,
        )
    )
    if view is None:
        raise AppError(404, "保存视图不存在", "没有找到该保存视图。", "saved_view_not_found")
    await session.delete(view)
    await session.commit()
    return Response(status_code=204)


@router.get("/projects", response_model=list[ProjectPublic])
async def projects(session: SessionDep, user: CurrentUser, workspace: CurrentWorkspace) -> list[ProjectPublic]:
    rows = list(
        (
            await session.scalars(
                select(Project)
                .where(Project.workspace_id == workspace.id, Project.owner_user_id == user.id)
                .order_by(Project.updated_at.desc())
            )
        ).all()
    )
    return [ProjectPublic.model_validate(row) for row in rows]


@router.post("/projects", response_model=ProjectPublic, status_code=201)
async def create_project(
    payload: ProjectCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> ProjectPublic:
    project = Project(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        name=payload.name,
        description=payload.description,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return ProjectPublic.model_validate(project)


@router.post("/projects/{project_id}/items", status_code=201)
async def add_project_item(
    project_id: UUID,
    payload: ProjectItemCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> dict[str, Any]:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace.id,
            Project.owner_user_id == user.id,
        )
    )
    if project is None:
        raise AppError(404, "研究项目不存在", "没有找到该项目。", "project_not_found")
    await ensure_resource_access(
        session,
        object_type=payload.object_type,
        object_id=payload.object_id,
        workspace_id=workspace.id,
        user_id=user.id,
    )
    existing = await session.scalar(
        select(ProjectItem).where(
            ProjectItem.project_id == project_id,
            ProjectItem.object_type == payload.object_type,
            ProjectItem.object_id == payload.object_id,
        )
    )
    if existing:
        return {"id": str(existing.id), "created": False}
    item = ProjectItem(
        project_id=project_id,
        object_type=payload.object_type,
        object_id=payload.object_id,
        title_override=payload.title_override,
        metadata_json=payload.metadata,
    )
    session.add(item)
    project.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(item)
    return {"id": str(item.id), "created": True}


@router.get("/projects/{project_id}", response_model=ProjectDetail)
async def project_detail(
    project_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> ProjectDetail:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace.id,
            Project.owner_user_id == user.id,
        )
    )
    if project is None:
        raise AppError(404, "研究项目不存在", "没有找到该项目。", "project_not_found")
    items = list(
        (
            await session.scalars(
                select(ProjectItem)
                .where(ProjectItem.project_id == project_id)
                .order_by(ProjectItem.sort_order, ProjectItem.created_at)
            )
        ).all()
    )
    notes = list(
        (
            await session.scalars(
                select(Note)
                .where(Note.project_id == project_id, Note.author_user_id == user.id)
                .order_by(Note.updated_at.desc())
            )
        ).all()
    )
    return ProjectDetail(
        **ProjectPublic.model_validate(project).model_dump(),
        items=[ProjectItemPublic.model_validate(item) for item in items],
        notes=[NotePublic.model_validate(note) for note in notes],
    )


@router.delete("/projects/{project_id}", status_code=204)
async def delete_project(
    project_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace.id,
            Project.owner_user_id == user.id,
        )
    )
    if project is None:
        raise AppError(404, "研究项目不存在", "没有找到该项目。", "project_not_found")
    await session.delete(project)
    await session.commit()
    return Response(status_code=204)


@router.get("/projects/{project_id}/items", response_model=list[ProjectItemPublic])
async def list_project_items(
    project_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> list[ProjectItemPublic]:
    project = await session.scalar(
        select(Project.id).where(
            Project.id == project_id,
            Project.workspace_id == workspace.id,
            Project.owner_user_id == user.id,
        )
    )
    if project is None:
        raise AppError(404, "研究项目不存在", "没有找到该项目。", "project_not_found")
    rows = list(
        (
            await session.scalars(
                select(ProjectItem)
                .where(ProjectItem.project_id == project_id)
                .order_by(ProjectItem.sort_order, ProjectItem.created_at)
            )
        ).all()
    )
    return [ProjectItemPublic.model_validate(row) for row in rows]


@router.delete("/projects/{project_id}/items/{item_id}", status_code=204)
async def delete_project_item(
    project_id: UUID,
    item_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    item = await session.scalar(
        select(ProjectItem)
        .join(Project, Project.id == ProjectItem.project_id)
        .where(
            ProjectItem.id == item_id,
            ProjectItem.project_id == project_id,
            Project.workspace_id == workspace.id,
            Project.owner_user_id == user.id,
        )
    )
    if item is None:
        raise AppError(404, "项目资料不存在", "没有找到该项目资料。", "project_item_not_found")
    await session.delete(item)
    await session.commit()
    return Response(status_code=204)


@router.post("/projects/{project_id}/notes", response_model=NotePublic, status_code=201)
async def create_note(
    project_id: UUID,
    payload: NoteCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> NotePublic:
    project = await session.scalar(
        select(Project).where(
            Project.id == project_id,
            Project.workspace_id == workspace.id,
            Project.owner_user_id == user.id,
        )
    )
    if project is None:
        raise AppError(404, "研究项目不存在", "没有找到该项目。", "project_not_found")
    note = Note(
        project_id=project_id,
        author_user_id=user.id,
        title=payload.title,
        body_markdown=payload.body_markdown,
    )
    session.add(note)
    project.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(note)
    return NotePublic.model_validate(note)


@router.get("/notes", response_model=list[NotePublic])
async def list_notes(
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
    limit: int = 200,
) -> list[NotePublic]:
    rows = list(
        (
            await session.scalars(
                select(Note)
                .outerjoin(Project, Project.id == Note.project_id)
                .where(
                    Note.author_user_id == user.id,
                    or_(Project.workspace_id == workspace.id, Note.project_id.is_(None)),
                )
                .order_by(Note.updated_at.desc())
                .limit(min(max(limit, 1), 500))
            )
        ).all()
    )
    return [NotePublic.model_validate(note) for note in rows]


@router.patch("/projects/{project_id}/notes/{note_id}", response_model=NotePublic)
async def update_note(
    project_id: UUID,
    note_id: UUID,
    payload: NoteUpdate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> NotePublic:
    note = await session.scalar(
        select(Note)
        .join(Project, Project.id == Note.project_id)
        .where(
            Note.id == note_id,
            Note.project_id == project_id,
            Note.author_user_id == user.id,
            Project.workspace_id == workspace.id,
        )
    )
    if note is None:
        raise AppError(404, "研究笔记不存在", "没有找到该笔记。", "note_not_found")
    note.title = payload.title
    note.body_markdown = payload.body_markdown
    note.version_no += 1
    await session.commit()
    await session.refresh(note)
    return NotePublic.model_validate(note)


@router.delete("/projects/{project_id}/notes/{note_id}", status_code=204)
async def delete_note(
    project_id: UUID,
    note_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    note = await session.scalar(
        select(Note)
        .join(Project, Project.id == Note.project_id)
        .where(
            Note.id == note_id,
            Note.project_id == project_id,
            Note.author_user_id == user.id,
            Project.workspace_id == workspace.id,
        )
    )
    if note is None:
        raise AppError(404, "研究笔记不存在", "没有找到该笔记。", "note_not_found")
    await session.delete(note)
    await session.commit()
    return Response(status_code=204)


@router.get("/alerts", response_model=list[AlertPublic])
async def alerts(session: SessionDep, user: CurrentUser, workspace: CurrentWorkspace) -> list[AlertPublic]:
    rows = list(
        (
            await session.scalars(
                select(AlertRule)
                .where(AlertRule.workspace_id == workspace.id, AlertRule.owner_user_id == user.id)
                .order_by(AlertRule.created_at.desc())
            )
        ).all()
    )
    return [AlertPublic.model_validate(row) for row in rows]


@router.post("/alerts", response_model=AlertPublic, status_code=201)
async def create_alert(
    payload: AlertCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> AlertPublic:
    required_targets = {
        "release_reminder": "release_event",
        "threshold": "series",
        "revision": "series",
    }
    expected_type = required_targets.get(payload.alert_type)
    if expected_type and (payload.target_id is None or payload.target_type != expected_type):
        raise AppError(422, "提醒目标缺失", f"{payload.alert_type} 提醒必须选择 {expected_type}。", "alert_target_required")
    if payload.alert_type == "fomc_update" and payload.target_id is not None and payload.target_type != "fomc_meeting":
        raise AppError(422, "提醒目标无效", "FOMC更新提醒目标必须是FOMC会议。", "alert_target_invalid")
    if payload.target_id is not None and payload.target_type in {"series", "release_event", "fomc_meeting"}:
        await ensure_resource_access(
            session,
            object_type=payload.target_type,
            object_id=payload.target_id,
            workspace_id=workspace.id,
            user_id=user.id,
        )
    if payload.alert_type == "threshold":
        operator = str(payload.rule.get("operator", ">="))
        if operator not in {">=", "<=", ">", "<", "=="} or "value" not in payload.rule:
            raise AppError(422, "阈值规则无效", "阈值提醒需要合法 operator 和 value。", "invalid_threshold_rule")
    if payload.alert_type == "digest" and not ({"hour_utc", "schedule"} & payload.rule.keys()):
        raise AppError(422, "简报计划缺失", "定期简报需要 hour_utc 或五段式 schedule。", "invalid_digest_rule")
    alert = AlertRule(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        name=payload.name,
        alert_type=payload.alert_type,
        target_type=payload.target_type,
        target_id=payload.target_id,
        rule=payload.rule,
        channels=payload.channels,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return AlertPublic.model_validate(alert)


@router.patch("/alerts/{alert_id}", response_model=AlertPublic)
async def toggle_alert(
    alert_id: UUID,
    active: bool,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> AlertPublic:
    alert = await session.scalar(
        select(AlertRule).where(
            AlertRule.id == alert_id,
            AlertRule.workspace_id == workspace.id,
            AlertRule.owner_user_id == user.id,
        )
    )
    if alert is None:
        raise AppError(404, "提醒规则不存在", "没有找到该提醒规则。", "alert_not_found")
    alert.active = active
    await session.commit()
    await session.refresh(alert)
    return AlertPublic.model_validate(alert)


@router.delete("/alerts/{alert_id}", status_code=204)
async def delete_alert(
    alert_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    alert = await session.scalar(
        select(AlertRule).where(
            AlertRule.id == alert_id,
            AlertRule.workspace_id == workspace.id,
            AlertRule.owner_user_id == user.id,
        )
    )
    if alert is None:
        raise AppError(404, "提醒规则不存在", "没有找到该提醒规则。", "alert_not_found")
    await session.delete(alert)
    await session.commit()
    return Response(status_code=204)


@router.get("/notifications", response_model=list[NotificationPublic])
async def notifications(
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
    unread_only: bool = False,
) -> list[NotificationPublic]:
    stmt = select(Notification).where(
        Notification.workspace_id == workspace.id,
        Notification.user_id == user.id,
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    rows = list((await session.scalars(stmt.order_by(Notification.created_at.desc()).limit(200))).all())
    return [NotificationPublic.model_validate(row) for row in rows]


@router.post("/notifications/{notification_id}/read", response_model=NotificationPublic)
async def mark_notification_read(
    notification_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> NotificationPublic:
    notification = await session.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.workspace_id == workspace.id,
            Notification.user_id == user.id,
        )
    )
    if notification is None:
        raise AppError(404, "通知不存在", "没有找到该通知。", "notification_not_found")
    notification.read_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(notification)
    return NotificationPublic.model_validate(notification)
