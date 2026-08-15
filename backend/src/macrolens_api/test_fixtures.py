from __future__ import annotations

import hashlib
import os
from calendar import monthrange
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .models import (
    AICitation,
    AIContext,
    AIRun,
    AlertRule,
    Dataset,
    Document,
    DocumentChunk,
    DocumentSeries,
    DocumentVersion,
    Favorite,
    FomcDot,
    FomcMeeting,
    FomcProbabilitySnapshot,
    FomcProjection,
    ForecastSnapshot,
    IngestionRun,
    Job,
    MarketReaction,
    Note,
    Notification,
    ObservationLatest,
    ObservationVintage,
    Project,
    ProjectItem,
    Provider,
    PublicationBatch,
    ReleaseDefinition,
    ReleaseEvent,
    ReleaseEventSeries,
    Report,
    SavedView,
    Series,
    SourceSeries,
    User,
    Workspace,
)
from .services.source_mapping_identity import source_mapping_fingerprint
from .services.source_mappings import approve_mapping_from_probe

FIXTURE_VERSION = "runtime-acceptance-v1"
SourceRow = tuple[SourceSeries, Series, Dataset, Provider]


def _month_sequence(start: date, count: int) -> list[date]:
    result: list[date] = []
    year, month = start.year, start.month
    for _ in range(count):
        result.append(date(year, month, 1))
        month += 1
        if month == 13:
            month = 1
            year += 1
    return result


def _period_end(period: date) -> date:
    return date(period.year, period.month, monthrange(period.year, period.month)[1])


def _fixture_value(series: Series, series_index: int, point_index: int) -> Decimal:
    if series.unit_code == "percent":
        return (
            Decimal("1.75")
            + Decimal(series_index) / Decimal(10)
            + Decimal(point_index % 18) / Decimal(20)
        )
    if series.unit_code in {"thousand_persons", "persons"}:
        return Decimal(120 + series_index * 20 + point_index * 3)
    if "usd" in series.unit_code:
        return Decimal(50 + series_index * 5) + Decimal(point_index) / Decimal(2)
    return Decimal(90 + series_index * 10) + Decimal(point_index) / Decimal(3)


async def _approve_runtime_acceptance_mappings(
    session: AsyncSession,
    source_rows: list[SourceRow],
) -> None:
    """Create explicit test-only Probe lineage for mappings from a clean catalog seed."""

    for source, _series, dataset, provider in source_rows:
        if source.mapping_status == "verified" and source.is_primary:
            continue
        fingerprint = source_mapping_fingerprint(source, dataset, provider)
        probe_job = Job(
            id=uuid4(),
            job_type="mapping_probe",
            status="succeeded",
            priority=0,
            payload={"source_series_id": source.id, "fixture": True},
            idempotency_key=f"{FIXTURE_VERSION}:mapping-probe:{source.id}",
            attempts=1,
            max_attempts=1,
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            result={
                "source_series_id": source.id,
                "provider_code": provider.code,
                "provider_series_id": source.provider_series_id,
                "http_reachable": True,
                "http_status": 200,
                "business_success": True,
                "identity_match": True,
                "authorization_available": True,
                "production_ready": True,
                "classification": "PASS",
                "response_sha256": hashlib.sha256(
                    f"{FIXTURE_VERSION}:{fingerprint}".encode()
                ).hexdigest(),
                "mapping_fingerprint": fingerprint,
                "issues": [],
                "evidence": {"fixture": True},
            },
        )
        session.add(probe_job)
        await session.flush()
        await approve_mapping_from_probe(
            session,
            source_series_id=source.id,
            probe_job_id=probe_job.id,
            verified_by="runtime-acceptance-fixture",
        )


async def seed_runtime_acceptance_fixtures(session: AsyncSession) -> dict[str, int | str]:
    settings = get_settings()
    if settings.environment != "test" or os.getenv("ALLOW_TEST_FIXTURES") != "true":
        raise RuntimeError(
            "Runtime acceptance fixtures are disabled outside an explicit test environment"
        )

    existing_run = await session.scalar(
        select(IngestionRun).where(IngestionRun.business_key == FIXTURE_VERSION)
    )
    if existing_run is not None:
        return {"status": "already_seeded", "run_id": str(existing_run.id)}

    admin = await session.scalar(
        select(User).where(User.email == settings.bootstrap_admin_email.lower())
    )
    if admin is None:
        raise RuntimeError("Bootstrap admin is required before acceptance fixtures")
    workspace = await session.scalar(select(Workspace).where(Workspace.owner_user_id == admin.id))
    if workspace is None:
        raise RuntimeError("Bootstrap workspace is required before acceptance fixtures")

    source_rows = list(
        (
            await session.execute(
                select(SourceSeries, Series, Dataset, Provider)
                .join(Series, Series.id == SourceSeries.series_id)
                .join(Dataset, Dataset.id == SourceSeries.dataset_id)
                .join(Provider, Provider.id == Dataset.provider_id)
                .where(
                    SourceSeries.mapping_status.in_(("needs_review", "verified")),
                    Series.status == "active",
                )
                .order_by(Series.theme, Series.canonical_code)
                .limit(12)
            )
        ).tuples().all()
    )
    if len(source_rows) < 3:
        raise RuntimeError("Acceptance fixtures require at least three active source mappings")
    await _approve_runtime_acceptance_mappings(session, source_rows)

    provider = source_rows[0][3]
    run = IngestionRun(
        provider_id=provider.id,
        run_type="test_fixture",
        business_key=FIXTURE_VERSION,
        scheduled_at=datetime.now(UTC),
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        status="succeeded",
        inserted_count=0,
        revised_count=1,
        unchanged_count=0,
        rejected_count=0,
        metrics={"fixture": True, "version": FIXTURE_VERSION},
    )
    session.add(run)
    await session.flush()
    batch = PublicationBatch(
        provider_id=provider.id,
        run_id=run.id,
        status="active",
        summary={"fixture": True},
        activated_at=datetime.now(UTC),
    )
    session.add(batch)
    await session.flush()

    periods = _month_sequence(date(2021, 1, 1), 67)
    observation_count = 0
    for series_index, (source, series, _dataset, _provider) in enumerate(source_rows):
        series.first_period = periods[0]
        series.latest_period = periods[-1]
        for point_index, period in enumerate(periods):
            value = _fixture_value(series, series_index, point_index)
            vintage = datetime(
                period.year, period.month, min(28, _period_end(period).day), 13, 30, tzinfo=UTC
            )
            first_value = (
                value - Decimal("0.10")
                if series_index == 0 and point_index == len(periods) - 2
                else value
            )
            session.add(
                ObservationVintage(
                    source_series_id=source.id,
                    period_start=period,
                    period_end=_period_end(period),
                    value=first_value,
                    observation_status="preliminary" if first_value != value else "normal",
                    published_at=vintage,
                    vintage_at=vintage,
                    source_updated_at=vintage,
                    run_id=run.id,
                    publication_batch_id=batch.id,
                    quality_flags=["acceptance_fixture"],
                )
            )
            if first_value != value:
                revised_vintage = vintage + timedelta(days=30)
                session.add(
                    ObservationVintage(
                        source_series_id=source.id,
                        period_start=period,
                        period_end=_period_end(period),
                        value=value,
                        observation_status="revised",
                        published_at=vintage,
                        vintage_at=revised_vintage,
                        source_updated_at=revised_vintage,
                        run_id=run.id,
                        publication_batch_id=batch.id,
                        quality_flags=["acceptance_fixture", "revised"],
                    )
                )
                latest_vintage = revised_vintage
                status = "revised"
            else:
                latest_vintage = vintage
                status = "normal"
            session.add(
                ObservationLatest(
                    source_series_id=source.id,
                    period_start=period,
                    period_end=_period_end(period),
                    value=value,
                    observation_status=status,
                    published_at=vintage,
                    vintage_at=latest_vintage,
                    run_id=run.id,
                    publication_batch_id=batch.id,
                )
            )
            observation_count += 1
    run.inserted_count = observation_count

    definitions = list(
        (await session.scalars(select(ReleaseDefinition).order_by(ReleaseDefinition.code))).all()
    )
    now = datetime.now(UTC)
    release_count = 0
    for index, definition in enumerate(definitions[:5]):
        series = source_rows[index % len(source_rows)][1]
        scheduled = now + timedelta(days=index - 2, hours=2)
        event = ReleaseEvent(
            release_definition_id=definition.id,
            external_event_id=f"acceptance-{definition.code.lower()}-{index}",
            title_zh=f"{definition.name_zh}运行时验收发布",
            title_en=f"{definition.code} runtime acceptance release",
            country_code="US",
            reference_period=f"2026-{max(1, 7 - index):02d}",
            scheduled_at=scheduled,
            source_timezone="America/New_York",
            actual_released_at=scheduled if index <= 2 else None,
            status="released" if index <= 2 else "scheduled",
            importance_score=3 if index < 2 else 2,
            importance_origin="fixture",
            official_url="https://example.com/official-release",
        )
        session.add(event)
        await session.flush()
        actual = Decimal("2.60") + Decimal(index) / Decimal(10)
        session.add(
            ReleaseEventSeries(
                event_id=event.id,
                series_id=series.id,
                role="headline",
                reference_period_start=periods[-1],
                actual_value=actual if index <= 2 else None,
                previous_value=actual - Decimal("0.10"),
                revised_previous_value=actual - Decimal("0.05"),
                transform_code="yoy",
                unit_label="%",
            )
        )
        session.add(
            ForecastSnapshot(
                event_id=event.id,
                series_id=series.id,
                provider_id=provider.id,
                observed_at=scheduled - timedelta(days=1),
                consensus_value=actual - Decimal("0.05"),
                median_value=actual - Decimal("0.05"),
                high_value=actual + Decimal("0.15"),
                low_value=actual - Decimal("0.20"),
                respondent_count=42,
                previous_reported_value=actual - Decimal("0.10"),
                forecast_unit="%",
                raw_payload={"fixture": True},
            )
        )
        session.add(
            MarketReaction(
                event_id=event.id,
                instrument_code="US10Y",
                window_code="30m",
                price_before=Decimal("4.20"),
                price_after=Decimal("4.15"),
                absolute_change=Decimal("-0.05"),
                percent_change=Decimal("-1.19"),
                data_provider_id=provider.id,
                observed_at=scheduled + timedelta(minutes=30),
            )
        )
        release_count += 1

    meeting = FomcMeeting(
        meeting_start=date(2026, 7, 28),
        meeting_end=date(2026, 7, 29),
        decision_at=datetime(2026, 7, 29, 18, 0, tzinfo=UTC),
        meeting_type="scheduled",
        status="completed",
        target_rate_lower=Decimal("4.25"),
        target_rate_upper=Decimal("4.50"),
        decision_code="hold",
        statement_tone="中性",
        press_conference_tone="中性偏鸽",
        summary_zh="委员会维持政策利率不变，并继续强调数据依赖。",
        official_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
    )
    session.add(meeting)
    await session.flush()
    for variable, projection_value in [
        ("real_gdp", "2.0"),
        ("unemployment", "4.2"),
        ("core_pce", "2.5"),
    ]:
        session.add(
            FomcProjection(
                meeting_id=meeting.id,
                variable_code=variable,
                horizon="2026",
                statistic="median",
                value=Decimal(projection_value),
                unit="%",
            )
        )
    for horizon, dot_value, count in [
        ("2026", "4.125", 8),
        ("2026", "3.875", 5),
        ("long_run", "3.000", 10),
    ]:
        session.add(
            FomcDot(
                meeting_id=meeting.id,
                horizon=horizon,
                dot_value=Decimal(dot_value),
                dot_count=count,
            )
        )
    for lower, upper, probability in [
        ("4.00", "4.25", "0.30"),
        ("4.25", "4.50", "0.60"),
        ("4.50", "4.75", "0.10"),
    ]:
        session.add(
            FomcProbabilitySnapshot(
                meeting_id=meeting.id,
                provider_id=provider.id,
                observed_at=now,
                target_lower=Decimal(lower),
                target_upper=Decimal(upper),
                probability=Decimal(probability),
                source_contract_id="acceptance-fixture",
                raw_payload={"fixture": True},
            )
        )

    document_provider = (
        await session.scalar(select(Provider).where(Provider.code == "BEA_API")) or provider
    )
    doc_text = (
        "核心PCE价格指数同比回落，服务价格仍有粘性。\n\n"
        "本报告解释数据口径、修订机制和主要分项贡献，并明确所有数字均为运行时验收夹具。"
    )
    document = Document(
        provider_id=document_provider.id,
        external_id="acceptance-pce-release",
        document_type="official_release",
        title="Runtime acceptance PCE release",
        title_zh="核心PCE运行时验收发布稿",
        source_url="https://apps.bea.gov/acceptance/pce-release.html",
        published_at=now - timedelta(days=1),
        language="zh-CN",
        copyright_status="official",
        status="active",
        metadata_json={"fixture": True},
    )
    session.add(document)
    await session.flush()
    version = DocumentVersion(
        document_id=document.id,
        version_no=1,
        content_hash=hashlib.sha256(doc_text.encode()).hexdigest(),
        extracted_text=doc_text,
        ai_summary_zh="核心PCE回落，但服务通胀仍需持续观察。",
        effective_at=now,
        parser_version="acceptance-fixture",
    )
    session.add(version)
    await session.flush()
    chunks: list[DocumentChunk] = []
    for index, content in enumerate(doc_text.split("\n\n")):
        chunk = DocumentChunk(
            document_version_id=version.id,
            chunk_no=index,
            page_start=index + 1,
            page_end=index + 1,
            heading_path="验收文档",
            content=content,
            token_count=max(1, len(content) // 4),
        )
        session.add(chunk)
        chunks.append(chunk)
    session.add(
        DocumentSeries(
            document_id=document.id, series_id=source_rows[0][1].id, relation_type="headline"
        )
    )

    project = Project(
        workspace_id=workspace.id,
        owner_user_id=admin.id,
        name="MacroLens运行时验收项目",
        description="覆盖指标、发布、文档、AI、报告、收藏和提醒的测试项目。",
        status="active",
    )
    session.add(project)
    await session.flush()
    session.add(
        ProjectItem(
            project_id=project.id,
            object_type="series",
            object_id=source_rows[0][1].id,
            title_override="核心指标",
        )
    )
    note = Note(
        project_id=project.id,
        author_user_id=admin.id,
        title="验收笔记",
        body_markdown="事实、推断和风险应当分开记录。",
        version_no=1,
    )
    session.add(note)
    saved_view = SavedView(
        workspace_id=workspace.id,
        owner_user_id=admin.id,
        name="通胀与就业对比",
        view_type="compare",
        definition={
            "series": [
                {
                    "series_id": str(source_rows[0][1].id),
                    "transform": "yoy",
                    "axis": "left",
                    "lag_periods": 0,
                },
                {
                    "series_id": str(source_rows[1][1].id),
                    "transform": "level",
                    "axis": "right",
                    "lag_periods": 0,
                },
            ]
        },
        description="运行时验收视图",
        is_shared=False,
    )
    session.add(saved_view)
    session.add(
        Favorite(
            workspace_id=workspace.id,
            user_id=admin.id,
            object_type="series",
            object_id=source_rows[0][1].id,
            group_name="验收",
            note="运行时验收收藏",
        )
    )
    alert = AlertRule(
        workspace_id=workspace.id,
        owner_user_id=admin.id,
        name="验收发布提醒",
        alert_type="release",
        target_type="release_event",
        target_id=None,
        rule={"minutes_before": 30},
        channels=["in_app"],
        active=True,
    )
    session.add(alert)
    await session.flush()
    session.add(
        Notification(
            workspace_id=workspace.id,
            user_id=admin.id,
            alert_rule_id=alert.id,
            notification_type="release",
            title="验收通知",
            body="发布提醒通知链路已生成。",
            action_url="/calendar",
            payload={"fixture": True},
        )
    )

    ai_run = AIRun(
        workspace_id=workspace.id,
        user_id=admin.id,
        project_id=project.id,
        prompt="分析核心PCE回落对政策路径的影响",
        mode="quick",
        model_name=settings.openai_model,
        model_version="acceptance-fixture",
        prompt_version="v1",
        data_as_of=now,
        status="completed",
        result_markdown="核心PCE边际回落，但服务价格仍有粘性。[1]",
        assumptions=["仅用于运行时验收"],
        token_usage={"input_tokens": 100, "output_tokens": 50},
        completed_at=now,
    )
    session.add(ai_run)
    await session.flush()
    session.add(
        AIContext(
            ai_run_id=ai_run.id,
            context_type="document",
            context_id=document.id,
            snapshot={
                "title": document.title_zh,
                "chunks": [{"chunk_id": str(chunks[0].id), "content": chunks[0].content}],
            },
        )
    )
    session.add(
        AICitation(
            ai_run_id=ai_run.id,
            citation_no=1,
            document_chunk_id=chunks[0].id,
            quote_text=chunks[0].content,
            locator={"title": document.title_zh, "page_start": 1},
        )
    )
    session.add(
        Report(
            workspace_id=workspace.id,
            owner_user_id=admin.id,
            project_id=project.id,
            ai_run_id=ai_run.id,
            title="MacroLens运行时验收报告",
            content_markdown=ai_run.result_markdown or "",
            status="draft",
            version_no=1,
            metadata_json={"fixture": True},
        )
    )

    await session.commit()
    return {
        "status": "seeded",
        "run_id": str(run.id),
        "series": len(source_rows),
        "observations": observation_count,
        "release_events": release_count,
        "documents": 1,
        "fomc_meetings": 1,
        "projects": 1,
    }
