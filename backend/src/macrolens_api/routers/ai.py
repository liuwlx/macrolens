from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Header, Response
from sqlalchemy import select

from ..config import get_settings
from ..demo_data import demo_ai_capability
from ..dependencies import CurrentUser, CurrentWorkspace, ReadSessionDep, SessionDep
from ..errors import AppError
from ..models import AICitation, AIRun, Project
from ..schemas import AICapabilityResponse, AICitationPublic, AIRunCreate, AIRunPublic
from ..services.ai_context import persist_contexts
from ..services.ai_runtime import ai_runtime_configured
from ..services.data_browser import ai_capability, normalize_data_as_of
from ..services.jobs import reserve_job

router = APIRouter(prefix="/ai", tags=["AI"])
settings = get_settings()


@router.get("/capabilities", response_model=AICapabilityResponse)
async def get_ai_capability(
    series_id: UUID,
    session: ReadSessionDep,
    _user: CurrentUser,
    _workspace: CurrentWorkspace,
    data_as_of: datetime | None = None,
) -> AICapabilityResponse:
    if settings.data_mode == "demo":
        return demo_ai_capability(series_id)
    assert session is not None
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
        configured=ai_runtime_configured(settings),
    )


@router.post("/runs", response_model=AIRunPublic, status_code=202)
async def create_ai_run(
    payload: AIRunCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=4, max_length=300),
    ],
) -> AIRunPublic:
    if not ai_runtime_configured(settings):
        raise AppError(
            503,
            "AI 服务尚未配置",
            "服务端没有可用的 AI API 密钥或模型配置。",
            "ai_not_configured",
        )
    request_started_at = datetime.now(UTC)
    cutoff = normalize_data_as_of(payload.data_as_of)
    if cutoff > request_started_at:
        raise AppError(
            422,
            "快照时间无效",
            "data_as_of 不能晚于请求开始时间。",
            "invalid_data_as_of",
        )
    request_hash = hashlib.sha256(
        json.dumps(
            payload.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    run_id = uuid4()
    reservation_key = (
        f"ai-run-request:{workspace.id}:{user.id}:"
        f"{hashlib.sha256(idempotency_key.encode('utf-8')).hexdigest()}"
    )
    job, created = await reserve_job(
        session,
        job_type="run_ai_analysis",
        payload={"ai_run_id": str(run_id), "request_hash": request_hash},
        idempotency_key=reservation_key,
        priority=20 if payload.mode == "deep_research" else 10,
        max_attempts=3,
    )
    if not created:
        if job.payload.get("request_hash") != request_hash:
            raise AppError(
                409,
                "幂等键已被使用",
                "同一 Idempotency-Key 不能用于不同的 AI 请求。",
                "idempotency_key_reused",
            )
        existing_run_id = job.payload.get("ai_run_id")
        existing = (
            await session.get(AIRun, UUID(str(existing_run_id)))
            if existing_run_id is not None
            else None
        )
        if existing is None:
            raise AppError(
                409,
                "幂等请求尚未完成",
                "先前请求仍在提交中，请稍后使用同一幂等键重试。",
                "idempotency_request_incomplete",
            )
        return AIRunPublic.model_validate(existing)

    if payload.project_id is not None:
        project = await session.scalar(
            select(Project.id).where(
                Project.id == payload.project_id,
                Project.workspace_id == workspace.id,
                Project.owner_user_id == user.id,
            )
        )
        if project is None:
            raise AppError(
                404,
                "研究项目不存在",
                "不能把AI分析保存到该项目。",
                "project_not_found",
            )

    run = AIRun(
        id=run_id,
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
        historical_cutoff=payload.data_as_of is not None,
    )
    await session.commit()
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
