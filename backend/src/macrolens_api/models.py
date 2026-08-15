from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _vector_type(dimensions: int) -> Any:
    try:
        from pgvector.sqlalchemy import Vector
    except ModuleNotFoundError:
        # Allows schema tooling to run before optional runtime deps are installed.
        from sqlalchemy.types import UserDefinedType

        class FallbackVector(UserDefinedType[list[float]]):
            cache_ok = True

            def get_col_spec(self, **_kwargs: Any) -> str:
                return f"vector({dimensions})"

        return FallbackVector()
    return Vector(dimensions)


class Base(DeclarativeBase):
    type_annotation_map = {
        dict[str, Any]: JSONB,
        list[Any]: JSONB,
    }


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Base, TimestampMixin):
    __tablename__ = "user_account"
    __table_args__ = (UniqueConstraint("email"), {"schema": "app"})

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="researcher", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshSession(Base):
    __tablename__ = "refresh_session"
    __table_args__ = (
        Index("refresh_session_user_active_idx", "user_id", "revoked_at"),
        {"schema": "app"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.user_account.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_from_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.refresh_session.id", ondelete="SET NULL")
    )
    user_agent: Mapped[str | None] = mapped_column(Text)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspace"
    __table_args__ = {"schema": "app"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.user_account.id"), nullable=False
    )


class Provider(Base, TimestampMixin):
    __tablename__ = "provider"
    __table_args__ = {"schema": "source"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    provider_type: Mapped[str] = mapped_column(String(40), nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text)
    api_docs_url: Mapped[str | None] = mapped_column(Text)
    terms_url: Mapped[str | None] = mapped_column(Text)
    attribution_text: Mapped[str | None] = mapped_column(Text)
    license_class: Mapped[str] = mapped_column(String(60), nullable=False)
    redistribution_ok: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class Dataset(Base, TimestampMixin):
    __tablename__ = "dataset"
    __table_args__ = (UniqueConstraint("provider_id", "code"), {"schema": "source"})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(160), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    frequency_hint: Mapped[str | None] = mapped_column(String(32))
    release_name: Mapped[str | None] = mapped_column(String(200))
    endpoint_template: Mapped[str | None] = mapped_column(Text)
    request_defaults: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    metadata_locator: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    provider: Mapped[Provider] = relationship()


class LicensePolicy(Base):
    __tablename__ = "license_policy"
    __table_args__ = {"schema": "source"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("source.dataset.id"))
    policy_version: Mapped[str | None] = mapped_column(String(80))
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    display_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    download_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_redistribution_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_training_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ai_context_allowed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attribution_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    attribution_text: Mapped[str | None] = mapped_column(Text)
    restrictions: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[str | None] = mapped_column(String(200))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Series(Base, TimestampMixin):
    __tablename__ = "series"
    __table_args__ = {"schema": "catalog"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    canonical_code: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    name_zh: Mapped[str] = mapped_column(String(300), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(300))
    short_name_zh: Mapped[str | None] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text)
    theme: Mapped[str] = mapped_column(String(80), nullable=False)
    series_type: Mapped[str] = mapped_column(String(32), nullable=False)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    unit_code: Mapped[str] = mapped_column(String(80), nullable=False)
    unit_label_zh: Mapped[str] = mapped_column(String(80), nullable=False)
    scale_factor: Mapped[Decimal] = mapped_column(Numeric(20, 8), default=1, nullable=False)
    seasonal_adjustment: Mapped[str] = mapped_column(String(80), default="not_applicable")
    geography_code: Mapped[str] = mapped_column(String(16), default="US")
    default_transform: Mapped[str] = mapped_column(String(40), default="level")
    decimal_places: Mapped[int] = mapped_column(SmallInteger, default=2)
    status: Mapped[str] = mapped_column(String(32), default="active")
    replacement_series_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id")
    )
    first_period: Mapped[date | None] = mapped_column(Date)
    latest_period: Mapped[date | None] = mapped_column(Date)


class SeriesAlias(Base):
    __tablename__ = "series_alias"
    __table_args__ = (UniqueConstraint("series_id", "alias", "language"), {"schema": "catalog"})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(300), nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="zh-CN")
    alias_type: Mapped[str] = mapped_column(String(32), default="search")


class SourceSeries(Base, TimestampMixin):
    __tablename__ = "source_series"
    __table_args__ = (
        UniqueConstraint("dataset_id", "provider_series_id", "source_locator"),
        Index(
            "one_primary_source_per_series",
            "series_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        {"schema": "source"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    series_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("catalog.series.id"))
    dataset_id: Mapped[int] = mapped_column(ForeignKey("source.dataset.id"), nullable=False)
    provider_series_id: Mapped[str | None] = mapped_column(String(240))
    source_locator: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    mapping_type: Mapped[str] = mapped_column(String(40), default="direct")
    mapping_status: Mapped[str] = mapped_column(String(40), default="pending")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    source_frequency: Mapped[str | None] = mapped_column(String(32))
    source_unit: Mapped[str | None] = mapped_column(String(80))
    source_seasonal_adjustment: Mapped[str | None] = mapped_column(String(80))
    source_title: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    verified_by: Mapped[str | None] = mapped_column(String(200))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_job_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.job.id"), unique=True
    )
    verification_fingerprint: Mapped[str | None] = mapped_column(String(64))

    series: Mapped[Series] = relationship()
    dataset: Mapped[Dataset] = relationship()


class TaxonomyNode(Base, TimestampMixin):
    __tablename__ = "taxonomy_node"
    __table_args__ = (UniqueConstraint("tree_code", "code"), {"schema": "catalog"})

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tree_code: Mapped[str] = mapped_column(String(80), nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.taxonomy_node.id", ondelete="CASCADE")
    )
    node_type: Mapped[str] = mapped_column(String(32), nullable=False)
    code: Mapped[str] = mapped_column(String(120), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(240), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    icon_key: Mapped[str | None] = mapped_column(String(80))
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="active")


class TaxonomySeries(Base):
    __tablename__ = "taxonomy_series"
    __table_args__ = {"schema": "catalog"}

    node_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("catalog.taxonomy_node.id", ondelete="CASCADE"),
        primary_key=True,
    )
    series_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id", ondelete="CASCADE"), primary_key=True
    )
    display_role: Mapped[str] = mapped_column(String(32), default="detail")
    display_order: Mapped[int] = mapped_column(Integer, default=0)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)


class RawObject(Base):
    __tablename__ = "raw_object"
    __table_args__ = (UniqueConstraint("provider_id", "sha256"), {"schema": "ingestion"})

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("source.dataset.id"))
    object_uri: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(200))
    byte_size: Mapped[int | None] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    request_url: Mapped[str | None] = mapped_column(Text)
    request_parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    http_status: Mapped[int | None] = mapped_column(Integer)
    source_last_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class IngestionRun(Base):
    __tablename__ = "run"
    __table_args__ = (UniqueConstraint("provider_id", "business_key"), {"schema": "ingestion"})

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(ForeignKey("source.dataset.id"))
    run_type: Mapped[str] = mapped_column(String(32), nullable=False)
    business_key: Mapped[str] = mapped_column(String(300), nullable=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_object_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion.raw_object.id")
    )
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    revised_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(120))
    error_message: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PublicationBatch(Base):
    __tablename__ = "publication_batch"
    __table_args__ = (
        Index("publication_batch_provider_status_idx", "provider_id", "status"),
        {"schema": "ingestion"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("ingestion.run.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    previous_batch_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion.publication_batch.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), default="building", nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QualityResult(Base):
    __tablename__ = "quality_result"
    __table_args__ = {"schema": "ingestion"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion.run.id", ondelete="CASCADE"), nullable=False
    )
    rule_code: Mapped[str] = mapped_column(String(120), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    series_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id")
    )
    period_start: Mapped[date | None] = mapped_column(Date)
    actual_value: Mapped[str | None] = mapped_column(Text)
    expected_value: Mapped[str | None] = mapped_column(Text)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ObservationVintage(Base):
    __tablename__ = "observation_vintage"
    __table_args__ = {"schema": "data"}

    source_series_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("source.source_series.id"), primary_key=True
    )
    period_start: Mapped[date] = mapped_column(Date, primary_key=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    value_text: Mapped[str | None] = mapped_column(Text)
    observation_status: Mapped[str] = mapped_column(String(32), default="normal")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vintage_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    source_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("ingestion.run.id"))
    publication_batch_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion.publication_batch.id", ondelete="SET NULL")
    )
    raw_object_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion.raw_object.id")
    )
    quality_flags: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ObservationLatest(Base):
    __tablename__ = "observation_latest"
    __table_args__ = {"schema": "data"}

    source_series_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("source.source_series.id"), primary_key=True
    )
    period_start: Mapped[date] = mapped_column(Date, primary_key=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    value_text: Mapped[str | None] = mapped_column(Text)
    observation_status: Mapped[str] = mapped_column(String(32), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vintage_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("ingestion.run.id"))
    publication_batch_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion.publication_batch.id", ondelete="SET NULL")
    )
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DerivedDefinition(Base):
    __tablename__ = "derived_definition"
    __table_args__ = {"schema": "data"}

    series_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id", ondelete="CASCADE"), primary_key=True
    )
    formula_type: Mapped[str] = mapped_column(String(40), nullable=False)
    formula_version: Mapped[str] = mapped_column(String(40), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    expression: Mapped[str | None] = mapped_column(Text)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    effective_to: Mapped[date | None] = mapped_column(Date)
    owner: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SeriesDependency(Base):
    __tablename__ = "series_dependency"
    __table_args__ = {"schema": "data"}

    derived_series_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id", ondelete="CASCADE"), primary_key=True
    )
    source_series_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id"), primary_key=True
    )
    dependency_role: Mapped[str] = mapped_column(String(32), default="input")
    weight_expression: Mapped[str | None] = mapped_column(Text)


class ReleaseDefinition(Base):
    __tablename__ = "definition"
    __table_args__ = {"schema": "release"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    name_zh: Mapped[str] = mapped_column(String(240), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(240))
    release_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_timezone: Mapped[str] = mapped_column(String(80), default="America/New_York")
    typical_time: Mapped[Any | None] = mapped_column(Time)
    schedule_source_url: Mapped[str | None] = mapped_column(Text)
    importance_method: Mapped[str] = mapped_column(String(32), default="internal")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class ReleaseEvent(Base, TimestampMixin):
    __tablename__ = "event"
    __table_args__ = (
        UniqueConstraint("release_definition_id", "scheduled_at", "reference_period"),
        {"schema": "release"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    release_definition_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("release.definition.id"), nullable=False
    )
    external_event_id: Mapped[str | None] = mapped_column(String(240))
    title_zh: Mapped[str] = mapped_column(String(300), nullable=False)
    title_en: Mapped[str | None] = mapped_column(String(300))
    country_code: Mapped[str] = mapped_column(String(16), default="US")
    reference_period: Mapped[str | None] = mapped_column(String(80))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source_timezone: Mapped[str] = mapped_column(String(80), nullable=False)
    actual_released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    importance_score: Mapped[int | None] = mapped_column(SmallInteger)
    importance_origin: Mapped[str] = mapped_column(String(32), default="internal")
    official_url: Mapped[str | None] = mapped_column(Text)

    definition: Mapped[ReleaseDefinition] = relationship()


class ReleaseEventSeries(Base):
    __tablename__ = "event_series"
    __table_args__ = {"schema": "release"}

    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("release.event.id", ondelete="CASCADE"), primary_key=True
    )
    series_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id"), primary_key=True
    )
    role: Mapped[str] = mapped_column(String(32), default="headline")
    reference_period_start: Mapped[date | None] = mapped_column(Date)
    actual_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    previous_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    revised_previous_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    transform_code: Mapped[str] = mapped_column(String(40), primary_key=True, default="level")
    unit_label: Mapped[str | None] = mapped_column(String(80))


class ForecastSnapshot(Base):
    __tablename__ = "forecast_snapshot"
    __table_args__ = (
        UniqueConstraint("event_id", "provider_id", "observed_at"),
        {"schema": "release"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("release.event.id", ondelete="CASCADE"), nullable=False
    )
    series_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id")
    )
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consensus_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    median_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    high_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    low_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    respondent_count: Mapped[int | None] = mapped_column(Integer)
    previous_reported_value: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    forecast_unit: Mapped[str | None] = mapped_column(String(80))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class MarketReaction(Base):
    __tablename__ = "market_reaction"
    __table_args__ = {"schema": "release"}

    event_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("release.event.id", ondelete="CASCADE"), primary_key=True
    )
    instrument_code: Mapped[str] = mapped_column(String(80), primary_key=True)
    window_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    price_before: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    price_after: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    absolute_change: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    percent_change: Mapped[Decimal | None] = mapped_column(Numeric(30, 10))
    data_provider_id: Mapped[int | None] = mapped_column(ForeignKey("source.provider.id"))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Document(Base, TimestampMixin):
    __tablename__ = "document"
    __table_args__ = (
        UniqueConstraint("provider_id", "external_id"),
        UniqueConstraint("source_url"),
        {"schema": "docs"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(240))
    document_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    title_zh: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    language: Mapped[str] = mapped_column(String(16), default="en")
    copyright_status: Mapped[str] = mapped_column(String(40), default="unknown")
    status: Mapped[str] = mapped_column(String(32), default="active")
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)

    provider: Mapped[Provider] = relationship()


class DocumentVersion(Base):
    __tablename__ = "document_version"
    __table_args__ = (
        UniqueConstraint("document_id", "version_no"),
        UniqueConstraint("document_id", "content_hash"),
        {"schema": "docs"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("docs.document.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_object_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("ingestion.raw_object.id")
    )
    extracted_text: Mapped[str | None] = mapped_column(Text)
    translated_text_zh: Mapped[str | None] = mapped_column(Text)
    ai_summary_zh: Mapped[str | None] = mapped_column(Text)
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    parser_version: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentChunk(Base):
    __tablename__ = "chunk"
    __table_args__ = (UniqueConstraint("document_version_id", "chunk_no"), {"schema": "docs"})

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_version_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("docs.document_version.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_no: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    heading_path: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    embedding: Mapped[list[float] | None] = mapped_column(_vector_type(1536))


class DocumentSeries(Base):
    __tablename__ = "document_series"
    __table_args__ = {"schema": "docs"}

    document_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("docs.document.id", ondelete="CASCADE"), primary_key=True
    )
    series_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id", ondelete="CASCADE"), primary_key=True
    )
    relation_type: Mapped[str] = mapped_column(String(32), primary_key=True, default="related")


class FomcMeeting(Base):
    __tablename__ = "meeting"
    __table_args__ = (UniqueConstraint("meeting_start", "meeting_end"), {"schema": "fomc"})

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    meeting_start: Mapped[date] = mapped_column(Date, nullable=False)
    meeting_end: Mapped[date] = mapped_column(Date, nullable=False)
    decision_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meeting_type: Mapped[str] = mapped_column(String(32), default="scheduled")
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    target_rate_lower: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    target_rate_upper: Mapped[Decimal | None] = mapped_column(Numeric(8, 4))
    decision_code: Mapped[str | None] = mapped_column(String(80))
    statement_tone: Mapped[str | None] = mapped_column(String(80))
    press_conference_tone: Mapped[str | None] = mapped_column(String(80))
    summary_zh: Mapped[str | None] = mapped_column(Text)
    official_url: Mapped[str | None] = mapped_column(Text)


class FomcProjection(Base):
    __tablename__ = "projection"
    __table_args__ = (
        UniqueConstraint("meeting_id", "variable_code", "horizon", "statistic"),
        {"schema": "fomc"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fomc.meeting.id", ondelete="CASCADE"), nullable=False
    )
    variable_code: Mapped[str] = mapped_column(String(80), nullable=False)
    horizon: Mapped[str] = mapped_column(String(32), nullable=False)
    statistic: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(12, 4))
    unit: Mapped[str] = mapped_column(String(80), nullable=False)


class FomcDot(Base):
    __tablename__ = "dot"
    __table_args__ = (UniqueConstraint("meeting_id", "horizon", "dot_value"), {"schema": "fomc"})

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fomc.meeting.id", ondelete="CASCADE"), nullable=False
    )
    horizon: Mapped[str] = mapped_column(String(32), nullable=False)
    dot_value: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    dot_count: Mapped[int] = mapped_column(SmallInteger, default=1)


class FomcProbabilitySnapshot(Base):
    __tablename__ = "probability_snapshot"
    __table_args__ = (
        UniqueConstraint(
            "meeting_id", "provider_id", "observed_at", "target_lower", "target_upper"
        ),
        Index("fomc_probability_meeting_observed_idx", "meeting_id", "observed_at"),
        {"schema": "fomc"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    meeting_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("fomc.meeting.id", ondelete="CASCADE"), nullable=False
    )
    provider_id: Mapped[int] = mapped_column(ForeignKey("source.provider.id"), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    target_lower: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    target_upper: Mapped[Decimal] = mapped_column(Numeric(8, 4), nullable=False)
    probability: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    source_contract_id: Mapped[str | None] = mapped_column(String(120))
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Favorite(Base):
    __tablename__ = "favorite"
    __table_args__ = (
        UniqueConstraint("workspace_id", "user_id", "object_type", "object_id"),
        {"schema": "app"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.workspace.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app.user_account.id"))
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    group_name: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SavedView(Base, TimestampMixin):
    __tablename__ = "saved_view"
    __table_args__ = (
        Index("saved_view_workspace_owner_idx", "workspace_id", "owner_user_id", "view_type"),
        {"schema": "app"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.workspace.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.user_account.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    view_type: Mapped[str] = mapped_column(String(40), nullable=False)
    definition: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    description: Mapped[str | None] = mapped_column(Text)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Project(Base, TimestampMixin):
    __tablename__ = "project"
    __table_args__ = {"schema": "app"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.workspace.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.user_account.id")
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="active")


class ProjectShareLink(Base):
    __tablename__ = "project_share_link"
    __table_args__ = (
        Index("project_share_token_idx", "token_hash", unique=True),
        {"schema": "app"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.project.id", ondelete="CASCADE"), nullable=False
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.user_account.id"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProjectItem(Base):
    __tablename__ = "project_item"
    __table_args__ = (
        UniqueConstraint("project_id", "object_type", "object_id"),
        {"schema": "app"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.project.id", ondelete="CASCADE"), nullable=False
    )
    object_type: Mapped[str] = mapped_column(String(40), nullable=False)
    object_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    title_override: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Note(Base, TimestampMixin):
    __tablename__ = "note"
    __table_args__ = {"schema": "app"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.project.id", ondelete="CASCADE")
    )
    author_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.user_account.id")
    )
    title: Mapped[str | None] = mapped_column(String(300))
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, default=1)


class Report(Base, TimestampMixin):
    __tablename__ = "report"
    __table_args__ = {"schema": "app"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.workspace.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.user_account.id"), nullable=False
    )
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.project.id", ondelete="SET NULL")
    )
    ai_run_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.ai_run.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)


class AlertRule(Base, TimestampMixin):
    __tablename__ = "alert_rule"
    __table_args__ = {"schema": "app"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.workspace.id", ondelete="CASCADE"), nullable=False
    )
    owner_user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.user_account.id")
    )
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    alert_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(40))
    target_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    rule: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    channels: Mapped[list[Any]] = mapped_column(JSONB, default=lambda: ["in_app"])
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(Base):
    __tablename__ = "notification"
    __table_args__ = {"schema": "app"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.workspace.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app.user_account.id"))
    alert_rule_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.alert_rule.id", ondelete="SET NULL")
    )
    notification_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    action_url: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIRun(Base):
    __tablename__ = "ai_run"
    __table_args__ = {"schema": "app"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    workspace_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.workspace.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), ForeignKey("app.user_account.id"))
    project_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.project.id")
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40), default="v1")
    data_as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    result_markdown: Mapped[str | None] = mapped_column(Text)
    assumptions: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    error_message: Mapped[str | None] = mapped_column(Text)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    estimated_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(18, 8))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIContext(Base):
    __tablename__ = "ai_context"
    __table_args__ = {"schema": "app"}

    ai_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.ai_run.id", ondelete="CASCADE"), primary_key=True
    )
    context_type: Mapped[str] = mapped_column(String(40), primary_key=True)
    context_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class AICitation(Base):
    __tablename__ = "ai_citation"
    __table_args__ = (UniqueConstraint("ai_run_id", "citation_no"), {"schema": "app"})

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    ai_run_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("app.ai_run.id", ondelete="CASCADE"), nullable=False
    )
    citation_no: Mapped[int] = mapped_column(Integer, nullable=False)
    document_chunk_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("docs.chunk.id")
    )
    series_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("catalog.series.id")
    )
    period_start: Mapped[date | None] = mapped_column(Date)
    vintage_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    quote_text: Mapped[str | None] = mapped_column(Text)
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        UniqueConstraint("idempotency_key"),
        Index("job_claim_idx", "status", "run_after", "priority"),
        {"schema": "app"},
    )

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    job_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(300), nullable=False)
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    locked_by: Mapped[str | None] = mapped_column(String(120))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = {"schema": "audit"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    actor_user_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    workspace_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    object_type: Mapped[str] = mapped_column(String(80), nullable=False)
    object_id: Mapped[str | None] = mapped_column(String(160))
    before_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    after_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    request_id: Mapped[str | None] = mapped_column(String(80))
    ip_address: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("series_search_idx", Series.name_zh, Series.name_en, Series.canonical_code)
Index(
    "observation_history_idx", ObservationVintage.source_series_id, ObservationVintage.period_start
)
Index(
    "release_schedule_idx",
    ReleaseEvent.scheduled_at,
    ReleaseEvent.country_code,
    ReleaseEvent.status,
)
Index("document_published_idx", Document.published_at.desc())
Index("notification_unread_idx", Notification.user_id, Notification.created_at.desc())
