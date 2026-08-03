from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    time: datetime
    version: str


class UserPublic(ORMModel):
    id: UUID
    email: EmailStr
    display_name: str
    role: str


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class AuthResponse(BaseModel):
    user: UserPublic
    access_expires_in_seconds: int


class AdminUserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["researcher", "admin"] = "researcher"


class AdminUserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    password: str | None = Field(default=None, min_length=12, max_length=256)
    role: Literal["researcher", "admin"] | None = None
    active: bool | None = None


class AdminUserPublic(UserPublic):
    active: bool
    last_login_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ProviderInfo(BaseModel):
    code: str
    name: str
    attribution: str | None = None
    license_class: str


class LicenseInfo(BaseModel):
    display_allowed: bool
    download_allowed: bool
    api_redistribution_allowed: bool
    ai_context_allowed: bool
    attribution_required: bool
    attribution_text: str | None = None


class SeriesSummary(BaseModel):
    id: UUID
    canonical_code: str
    name_zh: str
    name_en: str | None
    theme: str
    frequency: str
    unit_code: str
    unit_label_zh: str
    default_transform: str
    latest_period: date | None
    latest_value: Decimal | None = None
    latest_vintage_at: datetime | None = None
    provider: ProviderInfo | None = None


class SeriesDetail(SeriesSummary):
    description: str | None
    seasonal_adjustment: str
    geography_code: str
    decimal_places: int
    status: str
    first_period: date | None
    aliases: list[str] = Field(default_factory=list)
    license: LicenseInfo | None = None


class ObservationPoint(BaseModel):
    period_start: date
    period_end: date
    value: Decimal | None
    value_text: str | None = None
    status: str
    published_at: datetime | None = None
    vintage_at: datetime


class LineageInfo(BaseModel):
    provider: str
    dataset: str
    provider_series_id: str | None
    source_series_id: int
    source_locator: dict[str, Any]


class ObservationMeta(BaseModel):
    data_as_of: datetime
    vintage: str
    transform: str
    frequency: str
    unit: str
    lineage: LineageInfo | None = None
    license: LicenseInfo | None = None


class ObservationResponse(BaseModel):
    series: SeriesSummary
    data: list[ObservationPoint]
    meta: ObservationMeta


class RevisionItem(BaseModel):
    period_start: date
    first_value: Decimal | None
    latest_value: Decimal | None
    revision: Decimal | None
    first_vintage_at: datetime
    latest_vintage_at: datetime
    versions: int


class RevisionResponse(BaseModel):
    series_id: UUID
    items: list[RevisionItem]


class CompareSeriesSpec(BaseModel):
    series_id: UUID
    transform: Literal[
        "level", "difference", "mom", "qoq", "yoy", "annualized_3m", "annualized_6m", "rebased_100", "zscore"
    ] = "level"
    lag_periods: int = Field(default=0, ge=-120, le=120)
    axis: Literal["left", "right"] = "left"


class CompareRequest(BaseModel):
    series: list[CompareSeriesSpec] = Field(min_length=1, max_length=10)
    start: date | None = None
    end: date | None = None
    vintage: str = "latest"
    include_correlation: bool = True

    @model_validator(mode="after")
    def validate_request(self) -> "CompareRequest":
        if self.start and self.end and self.start > self.end:
            raise ValueError("start must be on or before end")
        ids = [item.series_id for item in self.series]
        if len(ids) != len(set(ids)):
            raise ValueError("series_id values must be unique")
        return self


class CompareSeriesResult(BaseModel):
    series: SeriesSummary
    transform: str
    axis: str
    lag_periods: int
    data: list[ObservationPoint]
    license: LicenseInfo | None = None


class CorrelationCell(BaseModel):
    left_series_id: UUID
    right_series_id: UUID
    coefficient: float | None
    observations: int


class CompareResponse(BaseModel):
    items: list[CompareSeriesResult]
    correlations: list[CorrelationCell]
    data_as_of: datetime


class ReleaseMetric(BaseModel):
    series_id: UUID
    name_zh: str
    transform: str
    actual_value: Decimal | None
    previous_value: Decimal | None
    revised_previous_value: Decimal | None
    unit_label: str | None


class ReleaseEventSummary(BaseModel):
    id: UUID
    title_zh: str
    title_en: str | None
    country_code: str
    reference_period: str | None
    scheduled_at: datetime
    actual_released_at: datetime | None
    status: str
    importance_score: int | None
    release_type: str
    provider_code: str
    provider_name: str
    official_url: str | None
    metrics: list[ReleaseMetric] = Field(default_factory=list)
    consensus_value: Decimal | None = None


class ForecastItem(BaseModel):
    observed_at: datetime
    consensus_value: Decimal | None
    median_value: Decimal | None
    high_value: Decimal | None
    low_value: Decimal | None
    respondent_count: int | None
    provider_code: str


class MarketReactionItem(BaseModel):
    instrument_code: str
    window_code: str
    absolute_change: Decimal | None
    percent_change: Decimal | None
    observed_at: datetime


class ReleaseEventDetail(ReleaseEventSummary):
    source_timezone: str
    forecasts: list[ForecastItem] = Field(default_factory=list)
    market_reactions: list[MarketReactionItem] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    id: UUID
    title: str
    title_zh: str | None
    document_type: str
    provider_code: str
    provider_name: str
    source_url: str
    published_at: datetime | None
    language: str
    copyright_status: str
    status: str
    summary_zh: str | None = None
    related_series: list[SeriesSummary] = Field(default_factory=list)
    license: LicenseInfo | None = None


class DocumentChunkPublic(BaseModel):
    id: UUID
    chunk_no: int
    page_start: int | None
    page_end: int | None
    heading_path: str | None
    content: str


class DocumentDetail(DocumentSummary):
    latest_version_id: UUID | None = None
    version_no: int | None = None
    content_hash: str | None = None
    extracted_text: str | None = None
    translated_text_zh: str | None = None
    chunks: list[DocumentChunkPublic] = Field(default_factory=list)


class FomcProjectionPublic(ORMModel):
    variable_code: str
    horizon: str
    statistic: str
    value: Decimal | None
    unit: str


class FomcDotPublic(ORMModel):
    horizon: str
    dot_value: Decimal
    dot_count: int


class FomcMeetingSummary(BaseModel):
    id: UUID
    meeting_start: date
    meeting_end: date
    decision_at: datetime | None
    status: str
    target_rate_lower: Decimal | None
    target_rate_upper: Decimal | None
    decision_code: str | None
    statement_tone: str | None
    summary_zh: str | None
    official_url: str | None


class FomcProbabilityPublic(ORMModel):
    observed_at: datetime
    target_lower: Decimal
    target_upper: Decimal
    probability: Decimal
    provider_code: str


class FomcMeetingDetail(FomcMeetingSummary):
    press_conference_tone: str | None
    projections: list[FomcProjectionPublic] = Field(default_factory=list)
    dots: list[FomcDotPublic] = Field(default_factory=list)
    documents: list[DocumentSummary] = Field(default_factory=list)


class FavoriteCreate(BaseModel):
    object_type: Literal["series", "document", "release_event", "fomc_meeting", "saved_view", "project", "ai_run"]
    object_id: UUID
    group_name: str | None = Field(default=None, max_length=120)
    note: str | None = Field(default=None, max_length=2000)


class FavoritePublic(ORMModel):
    id: UUID
    object_type: str
    object_id: UUID
    group_name: str | None
    note: str | None
    sort_order: int
    created_at: datetime


class SavedViewCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    view_type: Literal["compare", "dashboard", "search"] = "compare"
    definition: dict[str, Any]
    description: str | None = Field(default=None, max_length=5000)


class SavedViewUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=240)
    definition: dict[str, Any] | None = None
    description: str | None = Field(default=None, max_length=5000)
    is_shared: bool | None = None


class SavedViewPublic(ORMModel):
    id: UUID
    name: str
    view_type: str
    definition: dict[str, Any]
    description: str | None
    is_shared: bool
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    description: str | None = Field(default=None, max_length=5000)


class ProjectPublic(ORMModel):
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectItemCreate(BaseModel):
    object_type: Literal["series", "document", "release_event", "fomc_meeting", "saved_view", "ai_run", "note"]
    object_id: UUID
    title_override: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AlertCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    alert_type: Literal["release_reminder", "threshold", "revision", "new_document", "fomc_update", "digest"]
    target_type: str | None = None
    target_id: UUID | None = None
    rule: dict[str, Any]
    channels: list[Literal["in_app", "email"]] = Field(default_factory=lambda: ["in_app"])


class AlertPublic(ORMModel):
    id: UUID
    name: str
    alert_type: str
    target_type: str | None
    target_id: UUID | None
    rule: dict[str, Any]
    channels: list[Any]
    active: bool
    last_evaluated_at: datetime | None
    created_at: datetime
    updated_at: datetime


class NotificationPublic(ORMModel):
    id: UUID
    notification_type: str
    title: str
    body: str | None
    action_url: str | None
    payload: dict[str, Any]
    created_at: datetime
    read_at: datetime | None


class AIContextInput(BaseModel):
    context_type: Literal["series", "document", "release_event", "fomc_meeting", "saved_view", "note"]
    context_id: UUID


class AIRunCreate(BaseModel):
    prompt: str = Field(min_length=5, max_length=20000)
    mode: Literal["quick", "deep_research", "scenario"] = "quick"
    project_id: UUID | None = None
    contexts: list[AIContextInput] = Field(min_length=1, max_length=12)

    @model_validator(mode="after")
    def validate_contexts(self) -> "AIRunCreate":
        keys = [(item.context_type, item.context_id) for item in self.contexts]
        if len(keys) != len(set(keys)):
            raise ValueError("AI contexts must be unique")
        return self


class AIRunPublic(ORMModel):
    id: UUID
    prompt: str
    mode: str
    model_name: str
    model_version: str | None
    prompt_version: str
    data_as_of: datetime
    status: str
    result_markdown: str | None
    assumptions: list[Any]
    error_message: str | None
    token_usage: dict[str, Any]
    estimated_cost_usd: Decimal | None
    created_at: datetime
    completed_at: datetime | None


class AICitationPublic(ORMModel):
    id: UUID
    citation_no: int
    document_chunk_id: UUID | None
    series_id: UUID | None
    period_start: date | None
    vintage_at: datetime | None
    quote_text: str | None
    locator: dict[str, Any]


class JobCreate(BaseModel):
    job_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(min_length=4, max_length=300)
    priority: int = 0


class JobPublic(ORMModel):
    id: UUID
    job_type: str
    status: str
    priority: int
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    last_error: str | None
    result: dict[str, Any]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None

class ProjectItemPublic(ORMModel):
    id: UUID
    project_id: UUID
    object_type: str
    object_id: UUID
    title_override: str | None
    sort_order: int
    metadata_json: dict[str, Any]
    created_at: datetime


class NoteCreate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    body_markdown: str = Field(min_length=1, max_length=100000)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    body_markdown: str = Field(min_length=1, max_length=100000)


class NotePublic(ORMModel):
    id: UUID
    project_id: UUID | None
    author_user_id: UUID
    title: str | None
    body_markdown: str
    version_no: int
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectPublic):
    items: list[ProjectItemPublic] = Field(default_factory=list)
    notes: list[NotePublic] = Field(default_factory=list)


class SourceMappingUpdate(BaseModel):
    provider_series_id: str | None = None
    source_locator: dict[str, Any] | None = None
    mapping_status: Literal["needs_review", "verified", "license_required", "disabled"] | None = None
    is_primary: bool | None = None
    notes: str | None = Field(default=None, max_length=5000)


class AdminDocumentFetchRequest(BaseModel):
    provider_code: str = Field(min_length=2, max_length=80)
    source_url: str = Field(min_length=8, max_length=4000)
    title: str = Field(min_length=1, max_length=1000)
    title_zh: str | None = Field(default=None, max_length=1000)
    document_type: str = Field(default="official_release", min_length=2, max_length=80)
    external_id: str | None = Field(default=None, max_length=240)
    language: str = Field(default="en", min_length=2, max_length=16)
    published_at: datetime | None = None
    copyright_status: str = Field(default="official", max_length=40)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectShareCreate(BaseModel):
    expires_in_days: int = Field(default=7, ge=1, le=90)


class ProjectSharePublic(BaseModel):
    id: UUID
    project_id: UUID
    share_url: str | None = None
    expires_at: datetime
    revoked_at: datetime | None
    created_at: datetime


class ReportCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content_markdown: str | None = Field(default=None, max_length=500000)
    ai_run_id: UUID | None = None
    project_id: UUID | None = None
    status: Literal["draft", "published", "archived"] = "draft"


class ReportUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content_markdown: str | None = Field(default=None, max_length=500000)
    status: Literal["draft", "published", "archived"] | None = None


class ReportPublic(ORMModel):
    id: UUID
    project_id: UUID | None
    ai_run_id: UUID | None
    title: str
    content_markdown: str
    status: str
    version_no: int
    metadata_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime
