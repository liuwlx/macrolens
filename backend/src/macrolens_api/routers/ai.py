from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Response
from sqlalchemy import select

from ..config import get_settings
from ..dependencies import CurrentUser, CurrentWorkspace, SessionDep
from ..errors import AppError
from ..models import AICitation, AIRun, Project
from ..schemas import AICapabilityResponse, AICitationPublic, AIRunCreate, AIRunPublic
from ..services.ai_context import persist_contexts
from ..services.data_browser import ai_capability, normalize_data_as_of
from ..services.jobs import enqueue_job

router = APIRouter(prefix="/ai", tags=["AI"])
settings = get_settings()


@router.get("/capabilities", response_model=AICapabilityResponse)
async def get_ai_capability(
    series_id: UUID,
    session: SessionDep,
    _user: CurrentUser,
    _workspace: CurrentWorkspace,
    data_as_of: datetime | None = None,
) -> AICapabilityResponse:
    if data_as_of is not None and normalize_data_as_of(data_as_of) > datetime.now(UTC):
        raise AppError(
            422,
            "快照时间无效",
            "data_as_of 不能晚于请求开始时间。",
            "invalid_data_as_of",
        )
    return await ai_capability(
        session,
        series_id=series_id,
        configured=bool(settings.openai_api_key),
    )


@router.post("/runs", response_model=AIRunPublic, status_code=202)
async def create_ai_run(
    payload: AIRunCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> AIRunPublic:
    request_started_at = datetime.now(UTC)
    cutoff = normalize_data_as_of(payload.data_as_of)
    if cutoff > request_started_at:
        raise AppError(
            422,
            "快照时间无效",
            "data_as_of 不能晚于请求开始时间。",
            "invalid_data_as_of",
        )
    if payload.project_id is not None:
        project = await session.scalar(
            select(Project.id).where(
                Project.id == payload.project_id,
                Project.workspace_id == workspace.id,
                Project.owner_user_id == user.id,
            )
        )
        if project is None:
            raise AppError(404, "研究项目不存在", "不能把AI分析保存到该项目。", "project_not_found")

    run = AIRun(
        workspace_id=workspace.id,
        user_id=user.id,
        project_id=payload.project_id,
        prompt=payload.prompt,
        mode=payload.mode,
        model_name=(
            settings.openai_deep_research_model
            if payload.mode == "deep_research"
            else settings.openai_model
        ),
        prompt_version="v1",
        data_as_of=cutoff,
        status="queued",
    )
    session.add(run)
    await session.flush()
    await persist_contexts(
        session,
        ai_run_id=run.id,
        contexts=[(context.context_type, context.context_id) for context in payload.contexts],
        query=payload.prompt,
        workspace_id=workspace.id,
        user_id=user.id,
        data_as_of=cutoff,
    )
    await enqueue_job(
        session,
        job_type="run_ai_analysis",
        payload={"ai_run_id": str(run.id)},
        idempotency_key=f"ai-run:{run.id}",
        priority=20 if payload.mode == "deep_research" else 10,
        max_attempts=3,
    )
    await session.refresh(run)
    return AIRunPublic.model_validate(run)


@router.get("/runs", response_model=list[AIRunPublic])
async def list_ai_runs(
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
    limit: int = 50,
) -> list[AIRunPublic]:
    rows = list(
        (
            await session.scalars(
                select(AIRun)
                .where(AIRun.workspace_id == workspace.id, AIRun.user_id == user.id)
                .order_by(AIRun.created_at.desc())
                .limit(min(max(limit, 1), 200))
            )
        ).all()
    )
    return [AIRunPublic.model_validate(row) for row in rows]


@router.get("/runs/{run_id}", response_model=AIRunPublic)
async def get_ai_run(
    run_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> AIRunPublic:
    run = await session.scalar(
        select(AIRun).where(
            AIRun.id == run_id,
            AIRun.workspace_id == workspace.id,
            AIRun.user_id == user.id,
        )
    )
    if run is None:
        raise AppError(404, "AI分析不存在", "没有找到该分析任务。", "ai_run_not_found")
    return AIRunPublic.model_validate(run)


@router.get("/runs/{run_id}/citations", response_model=list[AICitationPublic])
async def get_citations(
    run_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> list[AICitationPublic]:
    run = await session.scalar(
        select(AIRun.id).where(
            AIRun.id == run_id,
            AIRun.workspace_id == workspace.id,
            AIRun.user_id == user.id,
        )
    )
    if run is None:
        raise AppError(404, "AI分析不存在", "没有找到该分析任务。", "ai_run_not_found")
    rows = list(
        (
            await session.scalars(
                select(AICitation)
                .where(AICitation.ai_run_id == run_id)
                .order_by(AICitation.citation_no)
            )
        ).all()
    )
    return [AICitationPublic.model_validate(row) for row in rows]


@router.delete("/runs/{run_id}", status_code=204)
async def cancel_ai_run(
    run_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    run = await session.scalar(
        select(AIRun).where(
            AIRun.id == run_id,
            AIRun.workspace_id == workspace.id,
            AIRun.user_id == user.id,
        )
    )
    if run is None:
        raise AppError(404, "AI分析不存在", "没有找到该分析任务。", "ai_run_not_found")
    if run.status in {"completed", "failed", "cancelled"}:
        return Response(status_code=204)
    run.status = "cancelled"
    run.completed_at = datetime.now(UTC)
    await session.commit()
    return Response(status_code=204)
