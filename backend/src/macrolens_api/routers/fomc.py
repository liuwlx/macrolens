from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..dependencies import SessionDep
from ..errors import AppError
from ..models import (
    Document,
    FomcDot,
    FomcMeeting,
    FomcProjection,
    FomcProbabilitySnapshot,
    Provider,
)
from ..schemas import (
    DocumentSummary,
    FomcDotPublic,
    FomcMeetingDetail,
    FomcMeetingSummary,
    FomcProjectionPublic,
    FomcProbabilityPublic,
)
from ..services.licenses import get_license_for_provider

router = APIRouter(prefix="/fomc", tags=["FOMC"])


@router.get("/meetings")
async def meetings(
    session: SessionDep,
    start: date | None = None,
    end: date | None = None,
    status: str | None = None,
    limit: int = Query(default=40, ge=1, le=200),
) -> dict[str, Any]:
    if start and end and start > end:
        raise AppError(422, "日期范围无效", "start 必须早于或等于 end。", "invalid_date_range")
    stmt = select(FomcMeeting)
    if start:
        stmt = stmt.where(FomcMeeting.meeting_end >= start)
    if end:
        stmt = stmt.where(FomcMeeting.meeting_start <= end)
    if status:
        stmt = stmt.where(FomcMeeting.status == status)
    rows = list((await session.scalars(stmt.order_by(FomcMeeting.meeting_start.desc()).limit(limit))).all())
    items = [
        FomcMeetingSummary(
            id=row.id,
            meeting_start=row.meeting_start,
            meeting_end=row.meeting_end,
            decision_at=row.decision_at,
            status=row.status,
            target_rate_lower=row.target_rate_lower,
            target_rate_upper=row.target_rate_upper,
            decision_code=row.decision_code,
            statement_tone=row.statement_tone,
            summary_zh=row.summary_zh,
            official_url=row.official_url,
        )
        for row in rows
    ]
    return {"items": [item.model_dump(mode="json") for item in items]}


@router.get("/meetings/{meeting_id}", response_model=FomcMeetingDetail)
async def meeting_detail(meeting_id: UUID, session: SessionDep) -> FomcMeetingDetail:
    meeting = await session.get(FomcMeeting, meeting_id)
    if meeting is None:
        raise AppError(404, "FOMC会议不存在", "没有找到该会议。", "fomc_meeting_not_found")
    projections = list(
        (
            await session.scalars(
                select(FomcProjection)
                .where(FomcProjection.meeting_id == meeting_id)
                .order_by(FomcProjection.variable_code, FomcProjection.horizon, FomcProjection.statistic)
            )
        ).all()
    )
    dots = list(
        (
            await session.scalars(
                select(FomcDot)
                .where(FomcDot.meeting_id == meeting_id)
                .order_by(FomcDot.horizon, FomcDot.dot_value.desc())
            )
        ).all()
    )
    # Meeting documents are joined through the physical table created by migrations.
    document_rows = (
        await session.execute(
            select(Document, Provider)
            .join(Provider, Provider.id == Document.provider_id)
            .where(Document.metadata_json["fomc_meeting_id"].astext == str(meeting_id))
            .order_by(Document.published_at)
        )
    ).all()
    documents: list[DocumentSummary] = []
    for document, provider in document_rows:
        license_info = await get_license_for_provider(session, provider.id)
        if not license_info.display_allowed:
            continue
        documents.append(
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
                license=license_info,
            )
        )
    return FomcMeetingDetail(
        id=meeting.id,
        meeting_start=meeting.meeting_start,
        meeting_end=meeting.meeting_end,
        decision_at=meeting.decision_at,
        status=meeting.status,
        target_rate_lower=meeting.target_rate_lower,
        target_rate_upper=meeting.target_rate_upper,
        decision_code=meeting.decision_code,
        statement_tone=meeting.statement_tone,
        press_conference_tone=meeting.press_conference_tone,
        summary_zh=meeting.summary_zh,
        official_url=meeting.official_url,
        projections=[FomcProjectionPublic.model_validate(item) for item in projections],
        dots=[FomcDotPublic.model_validate(item) for item in dots],
        documents=documents,
    )


@router.get("/meetings/{meeting_id}/probabilities", response_model=list[FomcProbabilityPublic])
async def meeting_probabilities(
    meeting_id: UUID,
    session: SessionDep,
    observed_at: str | None = None,
) -> list[FomcProbabilityPublic]:
    if await session.get(FomcMeeting, meeting_id) is None:
        raise AppError(404, "FOMC会议不存在", "没有找到该会议。", "fomc_meeting_not_found")
    if observed_at:
        try:
            target_time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise AppError(422, "时间格式无效", "observed_at 必须使用 ISO 8601。", "invalid_observed_at") from exc
    else:
        target_time = await session.scalar(
            select(FomcProbabilitySnapshot.observed_at)
            .where(FomcProbabilitySnapshot.meeting_id == meeting_id)
            .order_by(FomcProbabilitySnapshot.observed_at.desc())
            .limit(1)
        )
    if target_time is None:
        return []
    rows = (
        await session.execute(
            select(FomcProbabilitySnapshot, Provider)
            .join(Provider, Provider.id == FomcProbabilitySnapshot.provider_id)
            .where(
                FomcProbabilitySnapshot.meeting_id == meeting_id,
                FomcProbabilitySnapshot.observed_at == target_time,
            )
            .order_by(FomcProbabilitySnapshot.target_lower)
        )
    ).all()
    items: list[FomcProbabilityPublic] = []
    for row, provider in rows:
        license_info = await get_license_for_provider(session, provider.id)
        if not license_info.display_allowed:
            continue
        items.append(
            FomcProbabilityPublic(
                observed_at=row.observed_at,
                target_lower=row.target_lower,
                target_upper=row.target_upper,
                probability=row.probability,
                provider_code=provider.code,
            )
        )
    return items
