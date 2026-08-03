-- MacroLens PostgreSQL schema, v1
-- Target: PostgreSQL 16+

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE SCHEMA IF NOT EXISTS source;
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS ingestion;
CREATE SCHEMA IF NOT EXISTS data;
CREATE SCHEMA IF NOT EXISTS release;
CREATE SCHEMA IF NOT EXISTS docs;
CREATE SCHEMA IF NOT EXISTS fomc;
CREATE SCHEMA IF NOT EXISTS app;

-- -----------------------------------------------------------------------------
-- Source registry and licensing
-- -----------------------------------------------------------------------------
CREATE TABLE source.provider (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE,
    name                TEXT NOT NULL,
    provider_type       TEXT NOT NULL CHECK (provider_type IN (
                            'government','central_bank','international_org',
                            'commercial','academic','internal')),
    base_url            TEXT,
    api_docs_url        TEXT,
    terms_url           TEXT,
    attribution_text    TEXT,
    license_class       TEXT NOT NULL CHECK (license_class IN (
                            'US_GOV_PUBLIC','US_GOV_PUBLIC_ATTRIBUTION',
                            'PUBLIC_WITH_TERMS','PUBLIC_WITH_ATTRIBUTION',
                            'THIRD_PARTY_RESTRICTED','COMMERCIAL','INTERNAL')),
    redistribution_ok   BOOLEAN NOT NULL DEFAULT FALSE,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE source.dataset (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider_id         BIGINT NOT NULL REFERENCES source.provider(id),
    code                TEXT NOT NULL,
    name                TEXT NOT NULL,
    frequency_hint      TEXT,
    release_name        TEXT,
    endpoint_template   TEXT,
    request_defaults    JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata_locator    JSONB NOT NULL DEFAULT '{}'::jsonb,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_id, code)
);

CREATE TABLE source.license_policy (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    provider_id         BIGINT NOT NULL REFERENCES source.provider(id),
    dataset_id          BIGINT REFERENCES source.dataset(id),
    policy_version      TEXT,
    effective_from      DATE,
    effective_to        DATE,
    display_allowed     BOOLEAN NOT NULL DEFAULT FALSE,
    download_allowed    BOOLEAN NOT NULL DEFAULT FALSE,
    api_redistribution_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    ai_training_allowed BOOLEAN NOT NULL DEFAULT FALSE,
    attribution_required BOOLEAN NOT NULL DEFAULT TRUE,
    attribution_text    TEXT,
    restrictions        TEXT,
    reviewed_by         TEXT,
    reviewed_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- -----------------------------------------------------------------------------
-- Canonical catalog and taxonomy
-- -----------------------------------------------------------------------------
CREATE TABLE catalog.series (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    canonical_code      TEXT NOT NULL UNIQUE,
    name_zh             TEXT NOT NULL,
    name_en             TEXT,
    short_name_zh       TEXT,
    description         TEXT,
    theme               TEXT NOT NULL,
    series_type         TEXT NOT NULL CHECK (series_type IN ('raw','derived','composite')),
    frequency           TEXT NOT NULL CHECK (frequency IN ('intraday','daily','weekly','monthly','quarterly','annual','irregular')),
    unit_code           TEXT NOT NULL,
    unit_label_zh       TEXT NOT NULL,
    scale_factor        NUMERIC NOT NULL DEFAULT 1,
    seasonal_adjustment TEXT NOT NULL DEFAULT 'not_applicable',
    geography_code      TEXT NOT NULL DEFAULT 'US',
    default_transform   TEXT NOT NULL DEFAULT 'level',
    decimal_places      SMALLINT NOT NULL DEFAULT 2,
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('draft','active','discontinued','replaced','hidden')),
    replacement_series_id UUID REFERENCES catalog.series(id),
    first_period        DATE,
    latest_period       DATE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE catalog.series_alias (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    series_id           UUID NOT NULL REFERENCES catalog.series(id) ON DELETE CASCADE,
    alias               TEXT NOT NULL,
    language            TEXT NOT NULL DEFAULT 'zh-CN',
    alias_type          TEXT NOT NULL DEFAULT 'search',
    UNIQUE (series_id, alias, language)
);
CREATE INDEX series_alias_trgm_idx ON catalog.series_alias USING GIN (alias gin_trgm_ops);

CREATE TABLE source.source_series (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    series_id           UUID NOT NULL REFERENCES catalog.series(id),
    dataset_id          BIGINT NOT NULL REFERENCES source.dataset(id),
    provider_series_id  TEXT,
    source_locator      JSONB NOT NULL DEFAULT '{}'::jsonb,
    mapping_type        TEXT NOT NULL DEFAULT 'direct' CHECK (mapping_type IN (
                            'direct','metadata_line','dimension_filter','derived_transform','derived_aggregate')),
    mapping_status      TEXT NOT NULL DEFAULT 'pending' CHECK (mapping_status IN (
                            'pending','verified','needs_review','license_required','disabled')),
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    source_frequency    TEXT,
    source_unit         TEXT,
    source_seasonal_adjustment TEXT,
    source_title        TEXT,
    notes               TEXT,
    verified_by         TEXT,
    verified_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dataset_id, provider_series_id, source_locator)
);
CREATE UNIQUE INDEX one_primary_source_per_series
    ON source.source_series(series_id) WHERE is_primary;

CREATE TABLE catalog.taxonomy_node (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tree_code           TEXT NOT NULL,
    parent_id           UUID REFERENCES catalog.taxonomy_node(id) ON DELETE CASCADE,
    node_type           TEXT NOT NULL CHECK (node_type IN ('category','topic','series','virtual')),
    code                TEXT NOT NULL,
    name_zh             TEXT NOT NULL,
    name_en             TEXT,
    description         TEXT,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    icon_key            TEXT,
    visible             BOOLEAN NOT NULL DEFAULT TRUE,
    status              TEXT NOT NULL DEFAULT 'active',
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tree_code, code)
);
CREATE INDEX taxonomy_parent_idx ON catalog.taxonomy_node(tree_code, parent_id, sort_order);

CREATE TABLE catalog.taxonomy_series (
    node_id             UUID NOT NULL REFERENCES catalog.taxonomy_node(id) ON DELETE CASCADE,
    series_id           UUID NOT NULL REFERENCES catalog.series(id) ON DELETE CASCADE,
    display_role        TEXT NOT NULL DEFAULT 'detail' CHECK (display_role IN ('headline','detail','reference','comparison')),
    display_order       INTEGER NOT NULL DEFAULT 0,
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    PRIMARY KEY (node_id, series_id)
);

-- -----------------------------------------------------------------------------
-- Ingestion, raw lineage, quality and publication
-- -----------------------------------------------------------------------------
CREATE TABLE ingestion.raw_object (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id         BIGINT NOT NULL REFERENCES source.provider(id),
    dataset_id          BIGINT REFERENCES source.dataset(id),
    object_uri          TEXT NOT NULL,
    content_type        TEXT,
    byte_size           BIGINT,
    sha256              TEXT NOT NULL,
    request_url         TEXT,
    request_parameters  JSONB NOT NULL DEFAULT '{}'::jsonb,
    http_status         INTEGER,
    source_last_modified TIMESTAMPTZ,
    fetched_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_id, sha256)
);

CREATE TABLE ingestion.run (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id         BIGINT NOT NULL REFERENCES source.provider(id),
    dataset_id          BIGINT REFERENCES source.dataset(id),
    run_type            TEXT NOT NULL CHECK (run_type IN ('calendar','metadata','incremental','backfill','reconcile','document')),
    business_key        TEXT NOT NULL,
    scheduled_at        TIMESTAMPTZ,
    started_at          TIMESTAMPTZ,
    finished_at         TIMESTAMPTZ,
    status              TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','quarantined','cancelled')),
    raw_object_id       UUID REFERENCES ingestion.raw_object(id),
    inserted_count      INTEGER NOT NULL DEFAULT 0,
    revised_count       INTEGER NOT NULL DEFAULT 0,
    unchanged_count     INTEGER NOT NULL DEFAULT 0,
    rejected_count      INTEGER NOT NULL DEFAULT 0,
    error_code          TEXT,
    error_message       TEXT,
    metrics             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_id, business_key)
);

CREATE TABLE ingestion.quality_result (
    id                  BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id              UUID NOT NULL REFERENCES ingestion.run(id) ON DELETE CASCADE,
    rule_code           TEXT NOT NULL,
    severity            TEXT NOT NULL CHECK (severity IN ('info','warning','blocking')),
    passed              BOOLEAN NOT NULL,
    series_id           UUID REFERENCES catalog.series(id),
    period_start        DATE,
    actual_value        TEXT,
    expected_value      TEXT,
    message             TEXT NOT NULL,
    checked_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX quality_run_idx ON ingestion.quality_result(run_id, severity, passed);

CREATE TABLE ingestion.publication_batch (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_id          BIGINT NOT NULL REFERENCES source.dataset(id),
    run_id              UUID NOT NULL REFERENCES ingestion.run(id),
    version              TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('draft','approved','active','rolled_back','rejected')),
    observation_count   INTEGER NOT NULL DEFAULT 0,
    changed_series_count INTEGER NOT NULL DEFAULT 0,
    approved_by         TEXT,
    approved_at         TIMESTAMPTZ,
    activated_at        TIMESTAMPTZ,
    rolled_back_at      TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dataset_id, version)
);

-- -----------------------------------------------------------------------------
-- Observations, vintages and derived series
-- -----------------------------------------------------------------------------
CREATE TABLE data.observation_vintage (
    source_series_id    BIGINT NOT NULL REFERENCES source.source_series(id),
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    value               NUMERIC(30,10),
    value_text          TEXT,
    observation_status  TEXT NOT NULL DEFAULT 'normal' CHECK (observation_status IN (
                            'normal','preliminary','revised','estimated','missing','suppressed','discontinued')),
    published_at        TIMESTAMPTZ,
    vintage_at          TIMESTAMPTZ NOT NULL,
    source_updated_at   TIMESTAMPTZ,
    run_id              UUID NOT NULL REFERENCES ingestion.run(id),
    raw_object_id       UUID REFERENCES ingestion.raw_object(id),
    quality_flags       JSONB NOT NULL DEFAULT '[]'::jsonb,
    ingested_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_series_id, period_start, vintage_at),
    CHECK (period_end >= period_start)
);
CREATE INDEX observation_history_idx
    ON data.observation_vintage(source_series_id, period_start DESC, vintage_at DESC);
CREATE INDEX observation_vintage_idx
    ON data.observation_vintage(vintage_at DESC);

CREATE TABLE data.observation_latest (
    source_series_id    BIGINT NOT NULL REFERENCES source.source_series(id),
    period_start        DATE NOT NULL,
    period_end          DATE NOT NULL,
    value               NUMERIC(30,10),
    value_text          TEXT,
    observation_status  TEXT NOT NULL,
    published_at        TIMESTAMPTZ,
    vintage_at          TIMESTAMPTZ NOT NULL,
    run_id              UUID NOT NULL REFERENCES ingestion.run(id),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (source_series_id, period_start)
);
CREATE INDEX observation_latest_series_idx
    ON data.observation_latest(source_series_id, period_start DESC);

CREATE TABLE data.derived_definition (
    series_id           UUID PRIMARY KEY REFERENCES catalog.series(id) ON DELETE CASCADE,
    formula_type        TEXT NOT NULL CHECK (formula_type IN (
                            'mom','qoq','yoy','annualized','difference','moving_average',
                            'zscore','rebased','weighted_aggregate','custom_sql','custom_python')),
    formula_version     TEXT NOT NULL,
    parameters          JSONB NOT NULL DEFAULT '{}'::jsonb,
    expression          TEXT,
    effective_from      DATE NOT NULL,
    effective_to        DATE,
    owner               TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE data.series_dependency (
    derived_series_id   UUID NOT NULL REFERENCES catalog.series(id) ON DELETE CASCADE,
    source_series_id    UUID NOT NULL REFERENCES catalog.series(id),
    dependency_role     TEXT NOT NULL DEFAULT 'input',
    weight_expression   TEXT,
    PRIMARY KEY (derived_series_id, source_series_id)
);

-- -----------------------------------------------------------------------------
-- Release calendar, actuals, forecasts, surprises and market reactions
-- -----------------------------------------------------------------------------
CREATE TABLE release.definition (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code                TEXT NOT NULL UNIQUE,
    provider_id         BIGINT NOT NULL REFERENCES source.provider(id),
    name_zh             TEXT NOT NULL,
    name_en             TEXT,
    release_type        TEXT NOT NULL CHECK (release_type IN ('data','speech','meeting','document','survey')),
    source_timezone     TEXT NOT NULL DEFAULT 'America/New_York',
    typical_time        TIME,
    schedule_source_url TEXT,
    importance_method   TEXT NOT NULL DEFAULT 'internal',
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE release.event (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    release_definition_id UUID NOT NULL REFERENCES release.definition(id),
    external_event_id   TEXT,
    title_zh            TEXT NOT NULL,
    title_en            TEXT,
    country_code        TEXT NOT NULL DEFAULT 'US',
    reference_period    TEXT,
    scheduled_at        TIMESTAMPTZ NOT NULL,
    source_timezone     TEXT NOT NULL,
    actual_released_at  TIMESTAMPTZ,
    status              TEXT NOT NULL CHECK (status IN ('scheduled','delayed','released','revised','cancelled','suspended')),
    importance_score    SMALLINT CHECK (importance_score BETWEEN 1 AND 5),
    importance_origin   TEXT NOT NULL DEFAULT 'internal' CHECK (importance_origin IN ('internal','vendor')),
    official_url        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (release_definition_id, scheduled_at, reference_period)
);
CREATE INDEX release_event_schedule_idx ON release.event(scheduled_at, country_code, status);

CREATE TABLE release.event_series (
    event_id            UUID NOT NULL REFERENCES release.event(id) ON DELETE CASCADE,
    series_id           UUID NOT NULL REFERENCES catalog.series(id),
    role                TEXT NOT NULL DEFAULT 'headline' CHECK (role IN ('headline','component','reference')),
    reference_period_start DATE,
    actual_value        NUMERIC(30,10),
    previous_value      NUMERIC(30,10),
    revised_previous_value NUMERIC(30,10),
    transform_code      TEXT NOT NULL DEFAULT 'level',
    unit_label          TEXT,
    PRIMARY KEY (event_id, series_id, transform_code)
);

CREATE TABLE release.forecast_snapshot (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id            UUID NOT NULL REFERENCES release.event(id) ON DELETE CASCADE,
    series_id           UUID REFERENCES catalog.series(id),
    provider_id         BIGINT NOT NULL REFERENCES source.provider(id),
    observed_at         TIMESTAMPTZ NOT NULL,
    consensus_value     NUMERIC(30,10),
    median_value        NUMERIC(30,10),
    high_value          NUMERIC(30,10),
    low_value           NUMERIC(30,10),
    respondent_count    INTEGER,
    previous_reported_value NUMERIC(30,10),
    forecast_unit       TEXT,
    raw_payload         JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (event_id, provider_id, observed_at)
);
CREATE INDEX forecast_event_time_idx ON release.forecast_snapshot(event_id, observed_at DESC);

CREATE TABLE release.market_reaction (
    event_id            UUID NOT NULL REFERENCES release.event(id) ON DELETE CASCADE,
    instrument_code     TEXT NOT NULL,
    window_code         TEXT NOT NULL CHECK (window_code IN ('5m','30m','1h','1d')),
    price_before        NUMERIC(30,10),
    price_after         NUMERIC(30,10),
    absolute_change     NUMERIC(30,10),
    percent_change      NUMERIC(30,10),
    data_provider_id    BIGINT REFERENCES source.provider(id),
    observed_at         TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (event_id, instrument_code, window_code)
);

-- -----------------------------------------------------------------------------
-- Documents, versions, attachments and citation chunks
-- -----------------------------------------------------------------------------
CREATE TABLE docs.document (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id         BIGINT NOT NULL REFERENCES source.provider(id),
    external_id         TEXT,
    document_type       TEXT NOT NULL CHECK (document_type IN (
                            'news_release','minutes','statement','methodology','data_table',
                            'speech','testimony','research_report','projection','transcript','other')),
    title               TEXT NOT NULL,
    title_zh            TEXT,
    source_url          TEXT NOT NULL,
    published_at        TIMESTAMPTZ,
    language            TEXT NOT NULL DEFAULT 'en',
    copyright_status    TEXT NOT NULL DEFAULT 'unknown' CHECK (copyright_status IN (
                            'public_domain','public_with_attribution','restricted','licensed','unknown')),
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','superseded','withdrawn','hidden')),
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider_id, external_id),
    UNIQUE (source_url)
);
CREATE INDEX document_title_trgm_idx ON docs.document USING GIN (title gin_trgm_ops);
CREATE INDEX document_title_zh_trgm_idx ON docs.document USING GIN (title_zh gin_trgm_ops);

CREATE TABLE docs.document_version (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES docs.document(id) ON DELETE CASCADE,
    version_no          INTEGER NOT NULL,
    content_hash        TEXT NOT NULL,
    raw_object_id       UUID REFERENCES ingestion.raw_object(id),
    extracted_text      TEXT,
    translated_text_zh  TEXT,
    ai_summary_zh       TEXT,
    effective_at        TIMESTAMPTZ NOT NULL,
    superseded_at       TIMESTAMPTZ,
    parser_version      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, version_no),
    UNIQUE (document_id, content_hash)
);

CREATE TABLE docs.attachment (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id         UUID NOT NULL REFERENCES docs.document(id) ON DELETE CASCADE,
    title               TEXT NOT NULL,
    file_type           TEXT,
    source_url          TEXT NOT NULL,
    raw_object_id       UUID REFERENCES ingestion.raw_object(id),
    byte_size           BIGINT,
    sha256              TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, source_url)
);

CREATE TABLE docs.chunk (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_version_id UUID NOT NULL REFERENCES docs.document_version(id) ON DELETE CASCADE,
    chunk_no            INTEGER NOT NULL,
    page_start          INTEGER,
    page_end            INTEGER,
    heading_path        TEXT,
    content             TEXT NOT NULL,
    token_count         INTEGER,
    embedding_model     TEXT,
    embedding           BYTEA,
    UNIQUE (document_version_id, chunk_no)
);
CREATE INDEX document_chunk_content_trgm_idx ON docs.chunk USING GIN (content gin_trgm_ops);

CREATE TABLE docs.document_series (
    document_id         UUID NOT NULL REFERENCES docs.document(id) ON DELETE CASCADE,
    series_id           UUID NOT NULL REFERENCES catalog.series(id) ON DELETE CASCADE,
    relation_type       TEXT NOT NULL DEFAULT 'related' CHECK (relation_type IN ('official_release','methodology','related','cited')),
    PRIMARY KEY (document_id, series_id, relation_type)
);

CREATE TABLE docs.document_release (
    document_id         UUID NOT NULL REFERENCES docs.document(id) ON DELETE CASCADE,
    release_event_id    UUID NOT NULL REFERENCES release.event(id) ON DELETE CASCADE,
    relation_type       TEXT NOT NULL DEFAULT 'official',
    PRIMARY KEY (document_id, release_event_id)
);

-- -----------------------------------------------------------------------------
-- FOMC domain
-- -----------------------------------------------------------------------------
CREATE TABLE fomc.meeting (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_start       DATE NOT NULL,
    meeting_end         DATE NOT NULL,
    decision_at         TIMESTAMPTZ,
    meeting_type        TEXT NOT NULL DEFAULT 'scheduled' CHECK (meeting_type IN ('scheduled','unscheduled','conference_call')),
    status              TEXT NOT NULL CHECK (status IN ('scheduled','completed','cancelled')),
    target_rate_lower   NUMERIC(8,4),
    target_rate_upper   NUMERIC(8,4),
    decision_code       TEXT,
    statement_tone      TEXT,
    press_conference_tone TEXT,
    summary_zh          TEXT,
    official_url        TEXT,
    UNIQUE (meeting_start, meeting_end)
);

CREATE TABLE fomc.meeting_document (
    meeting_id          UUID NOT NULL REFERENCES fomc.meeting(id) ON DELETE CASCADE,
    document_id         UUID NOT NULL REFERENCES docs.document(id) ON DELETE CASCADE,
    document_role       TEXT NOT NULL CHECK (document_role IN ('statement','minutes','implementation_note','sep','press_conference','transcript')),
    PRIMARY KEY (meeting_id, document_id)
);

CREATE TABLE fomc.vote (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id          UUID NOT NULL REFERENCES fomc.meeting(id) ON DELETE CASCADE,
    member_name         TEXT NOT NULL,
    vote                TEXT NOT NULL CHECK (vote IN ('for','against','abstain','not_voting')),
    dissent_reason      TEXT,
    role_at_meeting     TEXT,
    UNIQUE (meeting_id, member_name)
);

CREATE TABLE fomc.projection (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id          UUID NOT NULL REFERENCES fomc.meeting(id) ON DELETE CASCADE,
    variable_code       TEXT NOT NULL,
    horizon             TEXT NOT NULL,
    statistic           TEXT NOT NULL CHECK (statistic IN ('median','central_low','central_high','range_low','range_high')),
    value               NUMERIC(12,4),
    unit                TEXT NOT NULL,
    UNIQUE (meeting_id, variable_code, horizon, statistic)
);

CREATE TABLE fomc.dot (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id          UUID NOT NULL REFERENCES fomc.meeting(id) ON DELETE CASCADE,
    horizon             TEXT NOT NULL,
    dot_value           NUMERIC(8,4) NOT NULL,
    dot_count           SMALLINT NOT NULL DEFAULT 1,
    UNIQUE (meeting_id, horizon, dot_value)
);

CREATE TABLE fomc.market_probability_snapshot (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id          UUID NOT NULL REFERENCES fomc.meeting(id) ON DELETE CASCADE,
    provider_id         BIGINT NOT NULL REFERENCES source.provider(id),
    observed_at         TIMESTAMPTZ NOT NULL,
    target_lower        NUMERIC(8,4) NOT NULL,
    target_upper        NUMERIC(8,4) NOT NULL,
    probability         NUMERIC(8,6) NOT NULL CHECK (probability BETWEEN 0 AND 1),
    UNIQUE (meeting_id, provider_id, observed_at, target_lower, target_upper)
);

-- -----------------------------------------------------------------------------
-- User workspace, favorites, alerts, AI and citations
-- -----------------------------------------------------------------------------
CREATE TABLE app.workspace (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT NOT NULL,
    owner_user_id       UUID NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.favorite (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES app.workspace(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL,
    object_type         TEXT NOT NULL CHECK (object_type IN ('series','document','release_event','fomc_meeting','saved_view','project','ai_run')),
    object_id           UUID NOT NULL,
    group_name          TEXT,
    note                TEXT,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, user_id, object_type, object_id)
);

CREATE TABLE app.saved_view (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES app.workspace(id) ON DELETE CASCADE,
    owner_user_id       UUID NOT NULL,
    name                TEXT NOT NULL,
    view_type           TEXT NOT NULL CHECK (view_type IN ('series_chart','comparison','release_filter','document_search','dashboard')),
    configuration       JSONB NOT NULL,
    is_shared           BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.project (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES app.workspace(id) ON DELETE CASCADE,
    owner_user_id       UUID NOT NULL,
    name                TEXT NOT NULL,
    description         TEXT,
    status              TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','archived')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.project_item (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES app.project(id) ON DELETE CASCADE,
    object_type         TEXT NOT NULL CHECK (object_type IN ('series','document','release_event','fomc_meeting','saved_view','ai_run','note')),
    object_id           UUID NOT NULL,
    title_override      TEXT,
    sort_order          INTEGER NOT NULL DEFAULT 0,
    metadata            JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (project_id, object_type, object_id)
);

CREATE TABLE app.note (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID REFERENCES app.project(id) ON DELETE CASCADE,
    author_user_id      UUID NOT NULL,
    title               TEXT,
    body_markdown       TEXT NOT NULL,
    version_no          INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.task (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID NOT NULL REFERENCES app.project(id) ON DELETE CASCADE,
    assignee_user_id    UUID,
    title               TEXT NOT NULL,
    due_at              TIMESTAMPTZ,
    status              TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','in_progress','done','cancelled')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.alert_rule (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES app.workspace(id) ON DELETE CASCADE,
    owner_user_id       UUID NOT NULL,
    name                TEXT NOT NULL,
    alert_type          TEXT NOT NULL CHECK (alert_type IN ('release_reminder','threshold','revision','new_document','fomc_update','digest')),
    target_type         TEXT,
    target_id           UUID,
    rule                JSONB NOT NULL,
    channels            JSONB NOT NULL DEFAULT '["in_app"]'::jsonb,
    active              BOOLEAN NOT NULL DEFAULT TRUE,
    last_evaluated_at   TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE app.notification (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES app.workspace(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL,
    alert_rule_id       UUID REFERENCES app.alert_rule(id) ON DELETE SET NULL,
    notification_type   TEXT NOT NULL,
    title               TEXT NOT NULL,
    body                TEXT,
    action_url          TEXT,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    read_at             TIMESTAMPTZ
);
CREATE INDEX notification_unread_idx ON app.notification(user_id, created_at DESC) WHERE read_at IS NULL;

CREATE TABLE app.ai_run (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID NOT NULL REFERENCES app.workspace(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL,
    project_id          UUID REFERENCES app.project(id) ON DELETE SET NULL,
    prompt              TEXT NOT NULL,
    mode                TEXT NOT NULL CHECK (mode IN ('quick','deep_research','scenario')),
    model_name          TEXT NOT NULL,
    model_version       TEXT,
    data_as_of          TIMESTAMPTZ NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('queued','running','completed','failed','cancelled')),
    result_markdown     TEXT,
    assumptions         JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at        TIMESTAMPTZ
);

CREATE TABLE app.ai_context (
    ai_run_id           UUID NOT NULL REFERENCES app.ai_run(id) ON DELETE CASCADE,
    context_type        TEXT NOT NULL CHECK (context_type IN ('series','document','release_event','fomc_meeting','saved_view','note')),
    context_id          UUID NOT NULL,
    snapshot            JSONB NOT NULL,
    PRIMARY KEY (ai_run_id, context_type, context_id)
);

CREATE TABLE app.ai_citation (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ai_run_id           UUID NOT NULL REFERENCES app.ai_run(id) ON DELETE CASCADE,
    citation_no         INTEGER NOT NULL,
    document_chunk_id   UUID REFERENCES docs.chunk(id),
    series_id           UUID REFERENCES catalog.series(id),
    period_start        DATE,
    vintage_at          TIMESTAMPTZ,
    quote_text          TEXT,
    locator             JSONB NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (ai_run_id, citation_no),
    CHECK (document_chunk_id IS NOT NULL OR series_id IS NOT NULL)
);

-- Recommended read views
CREATE VIEW data.canonical_observation_latest AS
SELECT
    ss.series_id,
    ss.id AS source_series_id,
    ol.period_start,
    ol.period_end,
    ol.value,
    ol.value_text,
    ol.observation_status,
    ol.published_at,
    ol.vintage_at
FROM source.source_series ss
JOIN data.observation_latest ol ON ol.source_series_id = ss.id
WHERE ss.is_primary AND ss.mapping_status = 'verified';

COMMENT ON TABLE data.observation_vintage IS
'Append-only observations. Never UPDATE an old vintage to a new value; insert a new vintage and refresh observation_latest.';
COMMENT ON TABLE release.forecast_snapshot IS
'Consensus/forecast values are time-varying and vendor-specific; persist each snapshot rather than one forecast column on the event.';
COMMENT ON TABLE source.license_policy IS
'Licensing is data, not a legal footnote. Use it to gate display, download, API redistribution and AI usage.';
