from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Response
from sqlalchemy import select

from ..dependencies import CurrentUser, CurrentWorkspace, SessionDep
from ..errors import AppError
from ..models import AICitation, AIRun, Project, Report
from ..schemas import ReportCreate, ReportPublic, ReportUpdate

router = APIRouter(prefix="/me/reports", tags=["Reports"])


async def _get_report(
    report_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Report:
    report = await session.scalar(
        select(Report).where(
            Report.id == report_id,
            Report.workspace_id == workspace.id,
            Report.owner_user_id == user.id,
        )
    )
    if report is None:
        raise AppError(404, "报告不存在", "没有找到该报告。", "report_not_found")
    return report


@router.get("", response_model=list[ReportPublic])
async def list_reports(
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> list[ReportPublic]:
    rows = list(
        (
            await session.scalars(
                select(Report)
                .where(Report.workspace_id == workspace.id, Report.owner_user_id == user.id)
                .order_by(Report.updated_at.desc())
            )
        ).all()
    )
    return [ReportPublic.model_validate(row) for row in rows]


@router.post("", response_model=ReportPublic, status_code=201)
async def create_report(
    payload: ReportCreate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> ReportPublic:
    content = payload.content_markdown
    metadata: dict[str, object] = {}
    if payload.ai_run_id:
        run = await session.scalar(
            select(AIRun).where(
                AIRun.id == payload.ai_run_id,
                AIRun.workspace_id == workspace.id,
                AIRun.user_id == user.id,
            )
        )
        if run is None or run.status != "completed" or not run.result_markdown:
            raise AppError(
                409, "AI分析尚不可用", "只能从已完成的AI分析创建报告。", "ai_run_not_ready"
            )
        content = content or run.result_markdown
        citations = list(
            (
                await session.scalars(
                    select(AICitation)
                    .where(AICitation.ai_run_id == run.id)
                    .order_by(AICitation.citation_no)
                )
            ).all()
        )
        metadata = {
            "data_as_of": run.data_as_of.isoformat(),
            "model_name": run.model_name,
            "prompt_version": run.prompt_version,
            "citation_count": len(citations),
        }
    if not content:
        raise AppError(
            422, "报告正文为空", "请提供正文或选择已完成的AI分析。", "report_content_required"
        )
    if payload.project_id:
        project = await session.scalar(
            select(Project).where(
                Project.id == payload.project_id,
                Project.workspace_id == workspace.id,
                Project.owner_user_id == user.id,
            )
        )
        if project is None:
            raise AppError(404, "研究项目不存在", "不能把报告保存到该项目。", "project_not_found")
    report = Report(
        workspace_id=workspace.id,
        owner_user_id=user.id,
        project_id=payload.project_id,
        ai_run_id=payload.ai_run_id,
        title=payload.title,
        content_markdown=content,
        status=payload.status,
        metadata_json=metadata,
    )
    session.add(report)
    await session.commit()
    await session.refresh(report)
    return ReportPublic.model_validate(report)


@router.get("/{report_id}", response_model=ReportPublic)
async def report_detail(
    report_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> ReportPublic:
    return ReportPublic.model_validate(await _get_report(report_id, session, user, workspace))


@router.patch("/{report_id}", response_model=ReportPublic)
async def update_report(
    report_id: UUID,
    payload: ReportUpdate,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> ReportPublic:
    report = await _get_report(report_id, session, user, workspace)
    if payload.title is not None:
        report.title = payload.title
    if payload.content_markdown is not None and payload.content_markdown != report.content_markdown:
        report.content_markdown = payload.content_markdown
        report.version_no += 1
    if payload.status is not None:
        report.status = payload.status
    await session.commit()
    await session.refresh(report)
    return ReportPublic.model_validate(report)


@router.delete("/{report_id}", status_code=204)
async def delete_report(
    report_id: UUID,
    session: SessionDep,
    user: CurrentUser,
    workspace: CurrentWorkspace,
) -> Response:
    report = await _get_report(report_id, session, user, workspace)
    await session.delete(report)
    await session.commit()
    return Response(status_code=204)
