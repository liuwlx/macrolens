from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import select

from ..dependencies import AdminUser, SessionDep
from ..errors import AppError
from ..models import (
    AuditLog,
    Dataset,
    IngestionRun,
    Job,
    ObservationLatest,
    ObservationVintage,
    Provider,
    PublicationBatch,
    QualityResult,
    RawObject,
    RefreshSession,
    Series,
    SourceSeries,
    User,
    Workspace,
)
from ..schemas import (
    AdminDocumentFetchRequest,
    AdminUserCreate,
    AdminUserPublic,
    AdminUserUpdate,
    JobCreate,
    JobPublic,
    SourceMappingApproval,
    SourceMappingUpdate,
)
from ..security import hash_password
from ..services.jobs import enqueue_job
from ..services.source_mappings import approve_mapping_from_probe

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users", response_model=list[AdminUserPublic])
async def list_users(session: SessionDep, _admin: AdminUser) -> list[AdminUserPublic]:
    rows = list((await session.scalars(select(User).order_by(User.created_at.desc()))).all())
    return [AdminUserPublic.model_validate(row) for row in rows]


@router.post("/users", response_model=AdminUserPublic, status_code=201)
async def create_user(
    payload: AdminUserCreate,
    session: SessionDep,
    _admin: AdminUser,
) -> AdminUserPublic:
    email = payload.email.lower().strip()
    if await session.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "邮箱已存在", "该邮箱已经注册。", "email_exists")
    user = User(
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
        role=payload.role,
        active=True,
    )
    session.add(user)
    await session.flush()
    session.add(Workspace(name=f"{user.display_name}的工作区", owner_user_id=user.id))
    await session.commit()
    await session.refresh(user)
    return AdminUserPublic.model_validate(user)


@router.patch("/users/{user_id}", response_model=AdminUserPublic)
async def update_user(
    user_id: UUID,
    payload: AdminUserUpdate,
    session: SessionDep,
    admin: AdminUser,
) -> AdminUserPublic:
    user = await session.get(User, user_id)
    if user is None:
        raise AppError(404, "用户不存在", "没有找到该用户。", "user_not_found")
    values = payload.model_dump(exclude_unset=True)
    if user.id == admin.id and values.get("active") is False:
        raise AppError(
            409, "不能停用自己", "请由其他管理员执行此操作。", "self_deactivation_forbidden"
        )
    if user.id == admin.id and values.get("role") not in {None, "admin"}:
        raise AppError(
            409, "不能降低自己的权限", "请由其他管理员执行此操作。", "self_role_change_forbidden"
        )
    password = values.pop("password", None)
    for key, value in values.items():
        setattr(user, key, value)
    if password:
        user.password_hash = hash_password(password)
    if password or values.get("active") is False:
        sessions = list(
            (
                await session.scalars(
                    select(RefreshSession).where(
                        RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None)
                    )
                )
            ).all()
        )
        from datetime import UTC, datetime

        for auth_session in sessions:
            auth_session.revoked_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(user)
    return AdminUserPublic.model_validate(user)


@router.post("/documents/fetch", response_model=JobPublic, status_code=202)
async def fetch_official_document(
    payload: AdminDocumentFetchRequest,
    session: SessionDep,
    _admin: AdminUser,
) -> JobPublic:
    provider = await session.scalar(
        select(Provider).where(Provider.code == payload.provider_code.upper())
    )
    if provider is None or not provider.active:
        raise AppError(404, "数据提供方不存在", "没有找到启用的数据提供方。", "provider_not_found")
    job = await enqueue_job(
        session,
        job_type="fetch_document",
        payload=payload.model_dump(mode="json"),
        idempotency_key=f"fetch-document:{provider.code}:{payload.source_url}",
        priority=12,
        max_attempts=4,
    )
    return JobPublic.model_validate(job)


@router.post("/jobs", response_model=JobPublic, status_code=202)
async def create_job(payload: JobCreate, session: SessionDep, _admin: AdminUser) -> JobPublic:
    job = await enqueue_job(
        session,
        job_type=payload.job_type,
        payload=payload.payload,
        idempotency_key=payload.idempotency_key,
        priority=payload.priority,
    )
    return JobPublic.model_validate(job)


@router.get("/jobs", response_model=list[JobPublic])
async def list_jobs(
    session: SessionDep,
    _admin: AdminUser,
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[JobPublic]:
    stmt = select(Job)
    if status:
        stmt = stmt.where(Job.status == status)
    rows = list((await session.scalars(stmt.order_by(Job.created_at.desc()).limit(limit))).all())
    return [JobPublic.model_validate(row) for row in rows]


@router.post("/jobs/{job_id}/retry", response_model=JobPublic)
async def retry_job(job_id: UUID, session: SessionDep, _admin: AdminUser) -> JobPublic:
    job = await session.get(Job, job_id)
    if job is None:
        raise AppError(404, "任务不存在", "没有找到该任务。", "job_not_found")
    if job.job_type == "mapping_probe" and isinstance(job.result.get("approval"), dict):
        raise AppError(
            409,
            "探测证据已被使用",
            "已批准映射的 MappingProbe 是不可变审计证据，不能重试覆盖。",
            "mapping_probe_already_consumed",
        )
    job.status = "queued"
    job.locked_by = None
    job.locked_at = None
    job.heartbeat_at = None
    job.last_error = None
    await session.commit()
    await session.refresh(job)
    return JobPublic.model_validate(job)


@router.get("/ingestion-runs")
async def ingestion_runs(
    session: SessionDep,
    _admin: AdminUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.scalars(
                select(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": str(row.id),
            "provider_id": row.provider_id,
            "dataset_id": row.dataset_id,
            "run_type": row.run_type,
            "business_key": row.business_key,
            "status": row.status,
            "inserted_count": row.inserted_count,
            "revised_count": row.revised_count,
            "unchanged_count": row.unchanged_count,
            "rejected_count": row.rejected_count,
            "started_at": row.started_at,
            "finished_at": row.finished_at,
            "error_message": row.error_message,
        }
        for row in rows
    ]


@router.get("/providers")
async def list_providers(
    session: SessionDep,
    _admin: AdminUser,
) -> list[dict[str, Any]]:
    rows = list((await session.scalars(select(Provider).order_by(Provider.code))).all())
    return [
        {
            "id": row.id,
            "code": row.code,
            "name": row.name,
            "provider_type": row.provider_type,
            "license_class": row.license_class,
            "redistribution_ok": row.redistribution_ok,
            "active": row.active,
        }
        for row in rows
    ]


@router.get("/source-mappings")
async def list_source_mappings(
    session: SessionDep,
    _admin: AdminUser,
    status: str | None = None,
    provider: str | None = None,
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[dict[str, Any]]:
    stmt = (
        select(SourceSeries, Series, Dataset, Provider)
        .join(Series, Series.id == SourceSeries.series_id)
        .join(Dataset, Dataset.id == SourceSeries.dataset_id)
        .join(Provider, Provider.id == Dataset.provider_id)
    )
    if status:
        stmt = stmt.where(SourceSeries.mapping_status == status)
    if provider:
        stmt = stmt.where(Provider.code == provider)
    rows = (
        await session.execute(stmt.order_by(Provider.code, Series.canonical_code).limit(limit))
    ).all()
    return [
        {
            "id": source.id,
            "series_id": str(series.id),
            "canonical_code": series.canonical_code,
            "name_zh": series.name_zh,
            "provider_code": provider_row.code,
            "dataset_code": dataset.code,
            "provider_series_id": source.provider_series_id,
            "source_locator": source.source_locator,
            "mapping_type": source.mapping_type,
            "mapping_status": source.mapping_status,
            "is_primary": source.is_primary,
            "notes": source.notes,
        }
        for source, series, dataset, provider_row in rows
    ]


@router.patch("/source-mappings/{source_mapping_id}")
async def update_source_mapping(
    source_mapping_id: int,
    payload: SourceMappingUpdate,
    session: SessionDep,
    _admin: AdminUser,
) -> dict[str, Any]:
    mapping = await session.get(SourceSeries, source_mapping_id)
    if mapping is None:
        raise AppError(404, "数据源映射不存在", "没有找到该映射。", "source_mapping_not_found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("is_primary") is True or values.get("mapping_status") == "verified":
        raise AppError(
            409,
            "数据源映射需要探测证据",
            "请先运行 MappingProbe，再通过原子批准接口晋级主数据源。",
            "mapping_probe_required",
        )
    if values.get("mapping_status") in {"needs_review", "license_required", "disabled"}:
        values["is_primary"] = False
    identity_changed = any(
        key in values and values[key] != getattr(mapping, key)
        for key in ("provider_series_id", "source_locator")
    )
    approval_revoked = identity_changed or values.get("mapping_status") in {
        "needs_review",
        "license_required",
        "disabled",
    }
    if approval_revoked:
        if identity_changed and "mapping_status" not in values:
            values["mapping_status"] = "needs_review"
        values["is_primary"] = False
        mapping.verified_by = None
        mapping.verified_at = None
        mapping.verification_job_id = None
        mapping.verification_fingerprint = None
    for key, value in values.items():
        setattr(mapping, key, value)
    await session.commit()
    return {
        "id": mapping.id,
        "mapping_status": mapping.mapping_status,
        "is_primary": mapping.is_primary,
    }


@router.post(
    "/source-mappings/{source_mapping_id}/probe",
    response_model=JobPublic,
    status_code=202,
)
async def create_mapping_probe(
    source_mapping_id: int,
    session: SessionDep,
    _admin: AdminUser,
) -> JobPublic:
    mapping = await session.get(SourceSeries, source_mapping_id)
    if mapping is None:
        raise AppError(404, "数据源映射不存在", "没有找到该映射。", "source_mapping_not_found")
    job = await enqueue_job(
        session,
        job_type="mapping_probe",
        payload={"source_series_id": mapping.id},
        idempotency_key=f"mapping-probe:{mapping.id}:{mapping.updated_at.isoformat()}",
        priority=15,
        max_attempts=2,
    )
    return JobPublic.model_validate(job)


@router.post("/source-mappings/{source_mapping_id}/approve")
async def approve_source_mapping(
    source_mapping_id: int,
    payload: SourceMappingApproval,
    session: SessionDep,
    admin: AdminUser,
) -> dict[str, Any]:
    try:
        mapping = await approve_mapping_from_probe(
            session,
            source_series_id=source_mapping_id,
            probe_job_id=payload.probe_job_id,
            verified_by=admin.email,
        )
    except RuntimeError as exc:
        raise AppError(
            409,
            "MappingProbe 证据不可用",
            str(exc),
            "mapping_probe_not_approved",
        ) from exc
    return {
        "id": mapping.id,
        "mapping_status": mapping.mapping_status,
        "is_primary": mapping.is_primary,
    }


@router.get("/quality-results")
async def quality_results(
    session: SessionDep,
    _admin: AdminUser,
    severity: str | None = None,
    passed: bool | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict[str, Any]]:
    stmt = select(QualityResult)
    if severity:
        stmt = stmt.where(QualityResult.severity == severity)
    if passed is not None:
        stmt = stmt.where(QualityResult.passed == passed)
    rows = list(
        (await session.scalars(stmt.order_by(QualityResult.checked_at.desc()).limit(limit))).all()
    )
    return [
        {
            "id": row.id,
            "run_id": str(row.run_id),
            "rule_code": row.rule_code,
            "severity": row.severity,
            "passed": row.passed,
            "series_id": str(row.series_id) if row.series_id else None,
            "period_start": row.period_start,
            "actual_value": row.actual_value,
            "expected_value": row.expected_value,
            "message": row.message,
            "checked_at": row.checked_at,
        }
        for row in rows
    ]


@router.get("/raw-objects")
async def raw_objects(
    session: SessionDep,
    _admin: AdminUser,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.scalars(
                select(RawObject).order_by(RawObject.fetched_at.desc()).limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": str(row.id),
            "provider_id": row.provider_id,
            "dataset_id": row.dataset_id,
            "object_uri": row.object_uri,
            "content_type": row.content_type,
            "byte_size": row.byte_size,
            "sha256": row.sha256,
            "request_url": row.request_url,
            "http_status": row.http_status,
            "fetched_at": row.fetched_at,
        }
        for row in rows
    ]


@router.get("/audit-logs")
async def audit_logs(
    session: SessionDep,
    _admin: AdminUser,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict[str, Any]]:
    rows = list(
        (
            await session.scalars(
                select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
            )
        ).all()
    )
    return [
        {
            "id": str(row.id),
            "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
            "action": row.action,
            "object_type": row.object_type,
            "object_id": row.object_id,
            "request_id": row.request_id,
            "ip_address": row.ip_address,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/publication-batches")
async def publication_batches(
    session: SessionDep,
    _admin: AdminUser,
    provider_id: int | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    stmt = select(PublicationBatch)
    if provider_id is not None:
        stmt = stmt.where(PublicationBatch.provider_id == provider_id)
    rows = list(
        (
            await session.scalars(stmt.order_by(PublicationBatch.created_at.desc()).limit(limit))
        ).all()
    )
    return [
        {
            "id": str(row.id),
            "provider_id": row.provider_id,
            "run_id": str(row.run_id),
            "previous_batch_id": str(row.previous_batch_id) if row.previous_batch_id else None,
            "status": row.status,
            "summary": row.summary,
            "activated_at": row.activated_at,
            "rolled_back_at": row.rolled_back_at,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/publication-batches/{batch_id}/rollback")
async def rollback_publication_batch(
    batch_id: UUID,
    session: SessionDep,
    _admin: AdminUser,
) -> dict[str, Any]:
    from datetime import UTC, datetime

    batch = await session.get(PublicationBatch, batch_id)
    if batch is None:
        raise AppError(404, "发布批次不存在", "没有找到该批次。", "publication_batch_not_found")
    if batch.status != "active":
        raise AppError(
            409, "批次不可回滚", "只有当前活动批次可以回滚。", "publication_batch_not_active"
        )

    touched = (
        await session.execute(
            select(ObservationVintage.source_series_id, ObservationVintage.period_start)
            .where(ObservationVintage.publication_batch_id == batch.id)
            .distinct()
        )
    ).all()
    restored = 0
    deleted = 0
    for source_series_id, period_start in touched:
        previous = await session.scalar(
            select(ObservationVintage)
            .where(
                ObservationVintage.source_series_id == source_series_id,
                ObservationVintage.period_start == period_start,
                ObservationVintage.publication_batch_id != batch.id,
            )
            .order_by(ObservationVintage.vintage_at.desc())
            .limit(1)
        )
        latest = await session.get(
            ObservationLatest,
            {"source_series_id": source_series_id, "period_start": period_start},
        )
        if previous is None:
            if latest is not None:
                await session.delete(latest)
                deleted += 1
            continue
        if latest is None:
            latest = ObservationLatest(
                source_series_id=previous.source_series_id,
                period_start=previous.period_start,
                period_end=previous.period_end,
                value=previous.value,
                value_text=previous.value_text,
                observation_status=previous.observation_status,
                published_at=previous.published_at,
                vintage_at=previous.vintage_at,
                run_id=previous.run_id,
                publication_batch_id=previous.publication_batch_id,
            )
            session.add(latest)
        else:
            latest.period_end = previous.period_end
            latest.value = previous.value
            latest.value_text = previous.value_text
            latest.observation_status = previous.observation_status
            latest.published_at = previous.published_at
            latest.vintage_at = previous.vintage_at
            latest.run_id = previous.run_id
            latest.publication_batch_id = previous.publication_batch_id
            latest.updated_at = datetime.now(UTC)
        restored += 1

    batch.status = "rolled_back"
    batch.rolled_back_at = datetime.now(UTC)
    if batch.previous_batch_id:
        previous_batch = await session.get(PublicationBatch, batch.previous_batch_id)
        if previous_batch:
            previous_batch.status = "active"
            previous_batch.activated_at = datetime.now(UTC)
    await session.commit()
    return {"batch_id": str(batch.id), "restored": restored, "deleted": deleted}
