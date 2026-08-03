"""Initial production schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-02

This migration is intentionally self-contained. It must not import live ORM metadata,
otherwise later model changes would silently rewrite the meaning of the initial migration.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMAS = ["source", "catalog", "ingestion", "data", "release", "docs", "fomc", "app", "audit"]

CREATE_STATEMENTS = [
    'CREATE TABLE app.job (\n\tid UUID NOT NULL, \n\tjob_type VARCHAR(80) NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tpriority INTEGER NOT NULL, \n\tpayload JSONB NOT NULL, \n\tidempotency_key VARCHAR(300) NOT NULL, \n\trun_after TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tattempts INTEGER NOT NULL, \n\tmax_attempts INTEGER NOT NULL, \n\tlocked_by VARCHAR(120), \n\tlocked_at TIMESTAMP WITH TIME ZONE, \n\theartbeat_at TIMESTAMP WITH TIME ZONE, \n\tlast_error TEXT, \n\tresult JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tstarted_at TIMESTAMP WITH TIME ZONE, \n\tfinished_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tUNIQUE (idempotency_key)\n)',
    'CREATE INDEX job_claim_idx ON app.job (status, run_after, priority)',
    'CREATE TABLE app.user_account (\n\tid UUID NOT NULL, \n\temail VARCHAR(320) NOT NULL, \n\tdisplay_name VARCHAR(120) NOT NULL, \n\tpassword_hash TEXT NOT NULL, \n\trole VARCHAR(32) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tlast_login_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (email)\n)',
    'CREATE TABLE audit.audit_log (\n\tid UUID NOT NULL, \n\tactor_user_id UUID, \n\tworkspace_id UUID, \n\taction VARCHAR(120) NOT NULL, \n\tobject_type VARCHAR(80) NOT NULL, \n\tobject_id VARCHAR(160), \n\tbefore_json JSONB, \n\tafter_json JSONB, \n\trequest_id VARCHAR(80), \n\tip_address VARCHAR(80), \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id)\n)',
    'CREATE TABLE catalog.series (\n\tid UUID NOT NULL, \n\tcanonical_code VARCHAR(160) NOT NULL, \n\tname_zh VARCHAR(300) NOT NULL, \n\tname_en VARCHAR(300), \n\tshort_name_zh VARCHAR(120), \n\tdescription TEXT, \n\ttheme VARCHAR(80) NOT NULL, \n\tseries_type VARCHAR(32) NOT NULL, \n\tfrequency VARCHAR(32) NOT NULL, \n\tunit_code VARCHAR(80) NOT NULL, \n\tunit_label_zh VARCHAR(80) NOT NULL, \n\tscale_factor NUMERIC(20, 8) NOT NULL, \n\tseasonal_adjustment VARCHAR(80) NOT NULL, \n\tgeography_code VARCHAR(16) NOT NULL, \n\tdefault_transform VARCHAR(40) NOT NULL, \n\tdecimal_places SMALLINT NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\treplacement_series_id UUID, \n\tfirst_period DATE, \n\tlatest_period DATE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (canonical_code), \n\tFOREIGN KEY(replacement_series_id) REFERENCES catalog.series (id)\n)',
    'CREATE INDEX series_search_idx ON catalog.series (name_zh, name_en, canonical_code)',
    'CREATE TABLE catalog.taxonomy_node (\n\tid UUID NOT NULL, \n\ttree_code VARCHAR(80) NOT NULL, \n\tparent_id UUID, \n\tnode_type VARCHAR(32) NOT NULL, \n\tcode VARCHAR(120) NOT NULL, \n\tname_zh VARCHAR(240) NOT NULL, \n\tname_en VARCHAR(240), \n\tdescription TEXT, \n\tsort_order INTEGER NOT NULL, \n\ticon_key VARCHAR(80), \n\tvisible BOOLEAN NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (tree_code, code), \n\tFOREIGN KEY(parent_id) REFERENCES catalog.taxonomy_node (id) ON DELETE CASCADE\n)',
    'CREATE TABLE fomc.meeting (\n\tid UUID NOT NULL, \n\tmeeting_start DATE NOT NULL, \n\tmeeting_end DATE NOT NULL, \n\tdecision_at TIMESTAMP WITH TIME ZONE, \n\tmeeting_type VARCHAR(32) NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\ttarget_rate_lower NUMERIC(8, 4), \n\ttarget_rate_upper NUMERIC(8, 4), \n\tdecision_code VARCHAR(80), \n\tstatement_tone VARCHAR(80), \n\tpress_conference_tone VARCHAR(80), \n\tsummary_zh TEXT, \n\tofficial_url TEXT, \n\tPRIMARY KEY (id), \n\tUNIQUE (meeting_start, meeting_end)\n)',
    'CREATE TABLE source.provider (\n\tid BIGSERIAL NOT NULL, \n\tcode VARCHAR(80) NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\tprovider_type VARCHAR(40) NOT NULL, \n\tbase_url TEXT, \n\tapi_docs_url TEXT, \n\tterms_url TEXT, \n\tattribution_text TEXT, \n\tlicense_class VARCHAR(60) NOT NULL, \n\tredistribution_ok BOOLEAN NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tmetadata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code)\n)',
    'CREATE TABLE app.refresh_session (\n\tid UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\trefresh_token_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\trevoked_at TIMESTAMP WITH TIME ZONE, \n\trotated_from_id UUID, \n\tuser_agent TEXT, \n\tip_address VARCHAR(64), \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(user_id) REFERENCES app.user_account (id) ON DELETE CASCADE, \n\tFOREIGN KEY(rotated_from_id) REFERENCES app.refresh_session (id) ON DELETE SET NULL\n)',
    'CREATE INDEX refresh_session_user_active_idx ON app.refresh_session (user_id, revoked_at)',
    'CREATE TABLE app.workspace (\n\tid UUID NOT NULL, \n\tname VARCHAR(200) NOT NULL, \n\towner_user_id UUID NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(owner_user_id) REFERENCES app.user_account (id)\n)',
    'CREATE TABLE catalog.series_alias (\n\tid BIGSERIAL NOT NULL, \n\tseries_id UUID NOT NULL, \n\talias VARCHAR(300) NOT NULL, \n\tlanguage VARCHAR(16) NOT NULL, \n\talias_type VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (series_id, alias, language), \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id) ON DELETE CASCADE\n)',
    'CREATE TABLE catalog.taxonomy_series (\n\tnode_id UUID NOT NULL, \n\tseries_id UUID NOT NULL, \n\tdisplay_role VARCHAR(32) NOT NULL, \n\tdisplay_order INTEGER NOT NULL, \n\tis_primary BOOLEAN NOT NULL, \n\tPRIMARY KEY (node_id, series_id), \n\tFOREIGN KEY(node_id) REFERENCES catalog.taxonomy_node (id) ON DELETE CASCADE, \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id) ON DELETE CASCADE\n)',
    'CREATE TABLE data.derived_definition (\n\tseries_id UUID NOT NULL, \n\tformula_type VARCHAR(40) NOT NULL, \n\tformula_version VARCHAR(40) NOT NULL, \n\tparameters JSONB NOT NULL, \n\texpression TEXT, \n\teffective_from DATE NOT NULL, \n\teffective_to DATE, \n\towner VARCHAR(120) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (series_id), \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id) ON DELETE CASCADE\n)',
    'CREATE TABLE data.series_dependency (\n\tderived_series_id UUID NOT NULL, \n\tsource_series_id UUID NOT NULL, \n\tdependency_role VARCHAR(32) NOT NULL, \n\tweight_expression TEXT, \n\tPRIMARY KEY (derived_series_id, source_series_id), \n\tFOREIGN KEY(derived_series_id) REFERENCES catalog.series (id) ON DELETE CASCADE, \n\tFOREIGN KEY(source_series_id) REFERENCES catalog.series (id)\n)',
    'CREATE TABLE docs.document (\n\tid UUID NOT NULL, \n\tprovider_id BIGINT NOT NULL, \n\texternal_id VARCHAR(240), \n\tdocument_type VARCHAR(40) NOT NULL, \n\ttitle TEXT NOT NULL, \n\ttitle_zh TEXT, \n\tsource_url TEXT NOT NULL, \n\tpublished_at TIMESTAMP WITH TIME ZONE, \n\tlanguage VARCHAR(16) NOT NULL, \n\tcopyright_status VARCHAR(40) NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tmetadata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (provider_id, external_id), \n\tUNIQUE (source_url), \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id)\n)',
    'CREATE INDEX document_published_idx ON docs.document (published_at DESC)',
    'CREATE TABLE fomc.dot (\n\tid UUID NOT NULL, \n\tmeeting_id UUID NOT NULL, \n\thorizon VARCHAR(32) NOT NULL, \n\tdot_value NUMERIC(8, 4) NOT NULL, \n\tdot_count SMALLINT NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (meeting_id, horizon, dot_value), \n\tFOREIGN KEY(meeting_id) REFERENCES fomc.meeting (id) ON DELETE CASCADE\n)',
    'CREATE TABLE fomc.probability_snapshot (\n\tid UUID NOT NULL, \n\tmeeting_id UUID NOT NULL, \n\tprovider_id BIGINT NOT NULL, \n\tobserved_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\ttarget_lower NUMERIC(8, 4) NOT NULL, \n\ttarget_upper NUMERIC(8, 4) NOT NULL, \n\tprobability NUMERIC(8, 6) NOT NULL, \n\tsource_contract_id VARCHAR(120), \n\traw_payload JSONB NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (meeting_id, provider_id, observed_at, target_lower, target_upper), \n\tFOREIGN KEY(meeting_id) REFERENCES fomc.meeting (id) ON DELETE CASCADE, \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id)\n)',
    'CREATE INDEX fomc_probability_meeting_observed_idx ON fomc.probability_snapshot (meeting_id, observed_at)',
    'CREATE TABLE fomc.projection (\n\tid UUID NOT NULL, \n\tmeeting_id UUID NOT NULL, \n\tvariable_code VARCHAR(80) NOT NULL, \n\thorizon VARCHAR(32) NOT NULL, \n\tstatistic VARCHAR(32) NOT NULL, \n\tvalue NUMERIC(12, 4), \n\tunit VARCHAR(80) NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (meeting_id, variable_code, horizon, statistic), \n\tFOREIGN KEY(meeting_id) REFERENCES fomc.meeting (id) ON DELETE CASCADE\n)',
    'CREATE TABLE release.definition (\n\tid UUID NOT NULL, \n\tcode VARCHAR(120) NOT NULL, \n\tprovider_id BIGINT NOT NULL, \n\tname_zh VARCHAR(240) NOT NULL, \n\tname_en VARCHAR(240), \n\trelease_type VARCHAR(32) NOT NULL, \n\tsource_timezone VARCHAR(80) NOT NULL, \n\ttypical_time TIME WITHOUT TIME ZONE, \n\tschedule_source_url TEXT, \n\timportance_method VARCHAR(32) NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tmetadata JSONB NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (code), \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id)\n)',
    'CREATE TABLE source.dataset (\n\tid BIGSERIAL NOT NULL, \n\tprovider_id BIGINT NOT NULL, \n\tcode VARCHAR(160) NOT NULL, \n\tname VARCHAR(300) NOT NULL, \n\tfrequency_hint VARCHAR(32), \n\trelease_name VARCHAR(200), \n\tendpoint_template TEXT, \n\trequest_defaults JSONB NOT NULL, \n\tmetadata_locator JSONB NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (provider_id, code), \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id)\n)',
    'CREATE TABLE app.alert_rule (\n\tid UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\towner_user_id UUID NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\talert_type VARCHAR(40) NOT NULL, \n\ttarget_type VARCHAR(40), \n\ttarget_id UUID, \n\trule JSONB NOT NULL, \n\tchannels JSONB NOT NULL, \n\tactive BOOLEAN NOT NULL, \n\tlast_evaluated_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(workspace_id) REFERENCES app.workspace (id) ON DELETE CASCADE, \n\tFOREIGN KEY(owner_user_id) REFERENCES app.user_account (id)\n)',
    'CREATE TABLE app.favorite (\n\tid UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\tobject_type VARCHAR(40) NOT NULL, \n\tobject_id UUID NOT NULL, \n\tgroup_name VARCHAR(120), \n\tnote TEXT, \n\tsort_order INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (workspace_id, user_id, object_type, object_id), \n\tFOREIGN KEY(workspace_id) REFERENCES app.workspace (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES app.user_account (id)\n)',
    'CREATE TABLE app.project (\n\tid UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\towner_user_id UUID NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\tdescription TEXT, \n\tstatus VARCHAR(32) NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(workspace_id) REFERENCES app.workspace (id) ON DELETE CASCADE, \n\tFOREIGN KEY(owner_user_id) REFERENCES app.user_account (id)\n)',
    'CREATE TABLE app.saved_view (\n\tid UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\towner_user_id UUID NOT NULL, \n\tname VARCHAR(240) NOT NULL, \n\tview_type VARCHAR(40) NOT NULL, \n\tdefinition JSONB NOT NULL, \n\tdescription TEXT, \n\tis_shared BOOLEAN NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(workspace_id) REFERENCES app.workspace (id) ON DELETE CASCADE, \n\tFOREIGN KEY(owner_user_id) REFERENCES app.user_account (id) ON DELETE CASCADE\n)',
    'CREATE INDEX saved_view_workspace_owner_idx ON app.saved_view (workspace_id, owner_user_id, view_type)',
    'CREATE TABLE docs.document_series (\n\tdocument_id UUID NOT NULL, \n\tseries_id UUID NOT NULL, \n\trelation_type VARCHAR(32) NOT NULL, \n\tPRIMARY KEY (document_id, series_id, relation_type), \n\tFOREIGN KEY(document_id) REFERENCES docs.document (id) ON DELETE CASCADE, \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id) ON DELETE CASCADE\n)',
    'CREATE TABLE ingestion.raw_object (\n\tid UUID NOT NULL, \n\tprovider_id BIGINT NOT NULL, \n\tdataset_id BIGINT, \n\tobject_uri TEXT NOT NULL, \n\tcontent_type VARCHAR(200), \n\tbyte_size BIGINT, \n\tsha256 VARCHAR(64) NOT NULL, \n\trequest_url TEXT, \n\trequest_parameters JSONB NOT NULL, \n\thttp_status INTEGER, \n\tsource_last_modified TIMESTAMP WITH TIME ZONE, \n\tfetched_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (provider_id, sha256), \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id), \n\tFOREIGN KEY(dataset_id) REFERENCES source.dataset (id)\n)',
    'CREATE TABLE release.event (\n\tid UUID NOT NULL, \n\trelease_definition_id UUID NOT NULL, \n\texternal_event_id VARCHAR(240), \n\ttitle_zh VARCHAR(300) NOT NULL, \n\ttitle_en VARCHAR(300), \n\tcountry_code VARCHAR(16) NOT NULL, \n\treference_period VARCHAR(80), \n\tscheduled_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tsource_timezone VARCHAR(80) NOT NULL, \n\tactual_released_at TIMESTAMP WITH TIME ZONE, \n\tstatus VARCHAR(32) NOT NULL, \n\timportance_score SMALLINT, \n\timportance_origin VARCHAR(32) NOT NULL, \n\tofficial_url TEXT, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (release_definition_id, scheduled_at, reference_period), \n\tFOREIGN KEY(release_definition_id) REFERENCES release.definition (id)\n)',
    'CREATE INDEX release_schedule_idx ON release.event (scheduled_at, country_code, status)',
    'CREATE TABLE source.license_policy (\n\tid BIGSERIAL NOT NULL, \n\tprovider_id BIGINT NOT NULL, \n\tdataset_id BIGINT, \n\tpolicy_version VARCHAR(80), \n\teffective_from DATE, \n\teffective_to DATE, \n\tdisplay_allowed BOOLEAN NOT NULL, \n\tdownload_allowed BOOLEAN NOT NULL, \n\tapi_redistribution_allowed BOOLEAN NOT NULL, \n\tai_training_allowed BOOLEAN NOT NULL, \n\tai_context_allowed BOOLEAN NOT NULL, \n\tattribution_required BOOLEAN NOT NULL, \n\tattribution_text TEXT, \n\trestrictions TEXT, \n\treviewed_by VARCHAR(200), \n\treviewed_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id), \n\tFOREIGN KEY(dataset_id) REFERENCES source.dataset (id)\n)',
    'CREATE TABLE source.source_series (\n\tid BIGSERIAL NOT NULL, \n\tseries_id UUID NOT NULL, \n\tdataset_id BIGINT NOT NULL, \n\tprovider_series_id VARCHAR(240), \n\tsource_locator JSONB NOT NULL, \n\tmapping_type VARCHAR(40) NOT NULL, \n\tmapping_status VARCHAR(40) NOT NULL, \n\tis_primary BOOLEAN NOT NULL, \n\tsource_frequency VARCHAR(32), \n\tsource_unit VARCHAR(80), \n\tsource_seasonal_adjustment VARCHAR(80), \n\tsource_title TEXT, \n\tnotes TEXT, \n\tverified_by VARCHAR(200), \n\tverified_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (dataset_id, provider_series_id, source_locator), \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id), \n\tFOREIGN KEY(dataset_id) REFERENCES source.dataset (id)\n)',
    'CREATE TABLE app.ai_run (\n\tid UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\tproject_id UUID, \n\tprompt TEXT NOT NULL, \n\tmode VARCHAR(32) NOT NULL, \n\tmodel_name VARCHAR(120) NOT NULL, \n\tmodel_version VARCHAR(120), \n\tprompt_version VARCHAR(40) NOT NULL, \n\tdata_as_of TIMESTAMP WITH TIME ZONE NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tresult_markdown TEXT, \n\tassumptions JSONB NOT NULL, \n\terror_message TEXT, \n\ttoken_usage JSONB NOT NULL, \n\testimated_cost_usd NUMERIC(18, 8), \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tcompleted_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(workspace_id) REFERENCES app.workspace (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES app.user_account (id), \n\tFOREIGN KEY(project_id) REFERENCES app.project (id)\n)',
    'CREATE TABLE app.note (\n\tid UUID NOT NULL, \n\tproject_id UUID, \n\tauthor_user_id UUID NOT NULL, \n\ttitle VARCHAR(300), \n\tbody_markdown TEXT NOT NULL, \n\tversion_no INTEGER NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(project_id) REFERENCES app.project (id) ON DELETE CASCADE, \n\tFOREIGN KEY(author_user_id) REFERENCES app.user_account (id)\n)',
    'CREATE TABLE app.notification (\n\tid UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\tuser_id UUID NOT NULL, \n\talert_rule_id UUID, \n\tnotification_type VARCHAR(40) NOT NULL, \n\ttitle VARCHAR(300) NOT NULL, \n\tbody TEXT, \n\taction_url TEXT, \n\tpayload JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tread_at TIMESTAMP WITH TIME ZONE, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(workspace_id) REFERENCES app.workspace (id) ON DELETE CASCADE, \n\tFOREIGN KEY(user_id) REFERENCES app.user_account (id), \n\tFOREIGN KEY(alert_rule_id) REFERENCES app.alert_rule (id) ON DELETE SET NULL\n)',
    'CREATE INDEX notification_unread_idx ON app.notification (user_id, created_at DESC)',
    'CREATE TABLE app.project_item (\n\tid UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tobject_type VARCHAR(40) NOT NULL, \n\tobject_id UUID NOT NULL, \n\ttitle_override TEXT, \n\tsort_order INTEGER NOT NULL, \n\tmetadata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (project_id, object_type, object_id), \n\tFOREIGN KEY(project_id) REFERENCES app.project (id) ON DELETE CASCADE\n)',
    'CREATE TABLE app.project_share_link (\n\tid UUID NOT NULL, \n\tproject_id UUID NOT NULL, \n\tcreated_by_user_id UUID NOT NULL, \n\ttoken_hash VARCHAR(64) NOT NULL, \n\texpires_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\trevoked_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(project_id) REFERENCES app.project (id) ON DELETE CASCADE, \n\tFOREIGN KEY(created_by_user_id) REFERENCES app.user_account (id)\n)',
    'CREATE UNIQUE INDEX project_share_token_idx ON app.project_share_link (token_hash)',
    'CREATE TABLE docs.document_version (\n\tid UUID NOT NULL, \n\tdocument_id UUID NOT NULL, \n\tversion_no INTEGER NOT NULL, \n\tcontent_hash VARCHAR(64) NOT NULL, \n\traw_object_id UUID, \n\textracted_text TEXT, \n\ttranslated_text_zh TEXT, \n\tai_summary_zh TEXT, \n\teffective_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tsuperseded_at TIMESTAMP WITH TIME ZONE, \n\tparser_version VARCHAR(80), \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (document_id, version_no), \n\tUNIQUE (document_id, content_hash), \n\tFOREIGN KEY(document_id) REFERENCES docs.document (id) ON DELETE CASCADE, \n\tFOREIGN KEY(raw_object_id) REFERENCES ingestion.raw_object (id)\n)',
    'CREATE TABLE ingestion.run (\n\tid UUID NOT NULL, \n\tprovider_id BIGINT NOT NULL, \n\tdataset_id BIGINT, \n\trun_type VARCHAR(32) NOT NULL, \n\tbusiness_key VARCHAR(300) NOT NULL, \n\tscheduled_at TIMESTAMP WITH TIME ZONE, \n\tstarted_at TIMESTAMP WITH TIME ZONE, \n\tfinished_at TIMESTAMP WITH TIME ZONE, \n\tstatus VARCHAR(32) NOT NULL, \n\traw_object_id UUID, \n\tinserted_count INTEGER NOT NULL, \n\trevised_count INTEGER NOT NULL, \n\tunchanged_count INTEGER NOT NULL, \n\trejected_count INTEGER NOT NULL, \n\terror_code VARCHAR(120), \n\terror_message TEXT, \n\tmetrics JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (provider_id, business_key), \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id), \n\tFOREIGN KEY(dataset_id) REFERENCES source.dataset (id), \n\tFOREIGN KEY(raw_object_id) REFERENCES ingestion.raw_object (id)\n)',
    'CREATE TABLE release.event_series (\n\tevent_id UUID NOT NULL, \n\tseries_id UUID NOT NULL, \n\trole VARCHAR(32) NOT NULL, \n\treference_period_start DATE, \n\tactual_value NUMERIC(30, 10), \n\tprevious_value NUMERIC(30, 10), \n\trevised_previous_value NUMERIC(30, 10), \n\ttransform_code VARCHAR(40) NOT NULL, \n\tunit_label VARCHAR(80), \n\tPRIMARY KEY (event_id, series_id, transform_code), \n\tFOREIGN KEY(event_id) REFERENCES release.event (id) ON DELETE CASCADE, \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id)\n)',
    'CREATE TABLE release.forecast_snapshot (\n\tid UUID NOT NULL, \n\tevent_id UUID NOT NULL, \n\tseries_id UUID, \n\tprovider_id BIGINT NOT NULL, \n\tobserved_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tconsensus_value NUMERIC(30, 10), \n\tmedian_value NUMERIC(30, 10), \n\thigh_value NUMERIC(30, 10), \n\tlow_value NUMERIC(30, 10), \n\trespondent_count INTEGER, \n\tprevious_reported_value NUMERIC(30, 10), \n\tforecast_unit VARCHAR(80), \n\traw_payload JSONB NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (event_id, provider_id, observed_at), \n\tFOREIGN KEY(event_id) REFERENCES release.event (id) ON DELETE CASCADE, \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id), \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id)\n)',
    'CREATE TABLE release.market_reaction (\n\tevent_id UUID NOT NULL, \n\tinstrument_code VARCHAR(80) NOT NULL, \n\twindow_code VARCHAR(16) NOT NULL, \n\tprice_before NUMERIC(30, 10), \n\tprice_after NUMERIC(30, 10), \n\tabsolute_change NUMERIC(30, 10), \n\tpercent_change NUMERIC(30, 10), \n\tdata_provider_id BIGINT, \n\tobserved_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tPRIMARY KEY (event_id, instrument_code, window_code), \n\tFOREIGN KEY(event_id) REFERENCES release.event (id) ON DELETE CASCADE, \n\tFOREIGN KEY(data_provider_id) REFERENCES source.provider (id)\n)',
    'CREATE TABLE app.ai_context (\n\tai_run_id UUID NOT NULL, \n\tcontext_type VARCHAR(40) NOT NULL, \n\tcontext_id UUID NOT NULL, \n\tsnapshot JSONB NOT NULL, \n\tPRIMARY KEY (ai_run_id, context_type, context_id), \n\tFOREIGN KEY(ai_run_id) REFERENCES app.ai_run (id) ON DELETE CASCADE\n)',
    'CREATE TABLE app.report (\n\tid UUID NOT NULL, \n\tworkspace_id UUID NOT NULL, \n\towner_user_id UUID NOT NULL, \n\tproject_id UUID, \n\tai_run_id UUID, \n\ttitle VARCHAR(300) NOT NULL, \n\tcontent_markdown TEXT NOT NULL, \n\tstatus VARCHAR(32) NOT NULL, \n\tversion_no INTEGER NOT NULL, \n\tmetadata JSONB NOT NULL, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(workspace_id) REFERENCES app.workspace (id) ON DELETE CASCADE, \n\tFOREIGN KEY(owner_user_id) REFERENCES app.user_account (id), \n\tFOREIGN KEY(project_id) REFERENCES app.project (id) ON DELETE SET NULL, \n\tFOREIGN KEY(ai_run_id) REFERENCES app.ai_run (id) ON DELETE SET NULL\n)',
    'CREATE TABLE docs.chunk (\n\tid UUID NOT NULL, \n\tdocument_version_id UUID NOT NULL, \n\tchunk_no INTEGER NOT NULL, \n\tpage_start INTEGER, \n\tpage_end INTEGER, \n\theading_path TEXT, \n\tcontent TEXT NOT NULL, \n\ttoken_count INTEGER, \n\tembedding_model VARCHAR(120), \n\tembedding vector(1536), \n\tPRIMARY KEY (id), \n\tUNIQUE (document_version_id, chunk_no), \n\tFOREIGN KEY(document_version_id) REFERENCES docs.document_version (id) ON DELETE CASCADE\n)',
    'CREATE TABLE ingestion.publication_batch (\n\tid UUID NOT NULL, \n\tprovider_id BIGINT NOT NULL, \n\trun_id UUID NOT NULL, \n\tprevious_batch_id UUID, \n\tstatus VARCHAR(32) NOT NULL, \n\tsummary JSONB NOT NULL, \n\tactivated_at TIMESTAMP WITH TIME ZONE, \n\trolled_back_at TIMESTAMP WITH TIME ZONE, \n\tcreated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(provider_id) REFERENCES source.provider (id), \n\tUNIQUE (run_id), \n\tFOREIGN KEY(run_id) REFERENCES ingestion.run (id) ON DELETE CASCADE, \n\tFOREIGN KEY(previous_batch_id) REFERENCES ingestion.publication_batch (id) ON DELETE SET NULL\n)',
    'CREATE INDEX publication_batch_provider_status_idx ON ingestion.publication_batch (provider_id, status)',
    'CREATE TABLE ingestion.quality_result (\n\tid BIGSERIAL NOT NULL, \n\trun_id UUID NOT NULL, \n\trule_code VARCHAR(120) NOT NULL, \n\tseverity VARCHAR(20) NOT NULL, \n\tpassed BOOLEAN NOT NULL, \n\tseries_id UUID, \n\tperiod_start DATE, \n\tactual_value TEXT, \n\texpected_value TEXT, \n\tmessage TEXT NOT NULL, \n\tchecked_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (id), \n\tFOREIGN KEY(run_id) REFERENCES ingestion.run (id) ON DELETE CASCADE, \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id)\n)',
    'CREATE TABLE app.ai_citation (\n\tid UUID NOT NULL, \n\tai_run_id UUID NOT NULL, \n\tcitation_no INTEGER NOT NULL, \n\tdocument_chunk_id UUID, \n\tseries_id UUID, \n\tperiod_start DATE, \n\tvintage_at TIMESTAMP WITH TIME ZONE, \n\tquote_text TEXT, \n\tlocator JSONB NOT NULL, \n\tPRIMARY KEY (id), \n\tUNIQUE (ai_run_id, citation_no), \n\tFOREIGN KEY(ai_run_id) REFERENCES app.ai_run (id) ON DELETE CASCADE, \n\tFOREIGN KEY(document_chunk_id) REFERENCES docs.chunk (id), \n\tFOREIGN KEY(series_id) REFERENCES catalog.series (id)\n)',
    'CREATE TABLE data.observation_latest (\n\tsource_series_id BIGINT NOT NULL, \n\tperiod_start DATE NOT NULL, \n\tperiod_end DATE NOT NULL, \n\tvalue NUMERIC(30, 10), \n\tvalue_text TEXT, \n\tobservation_status VARCHAR(32) NOT NULL, \n\tpublished_at TIMESTAMP WITH TIME ZONE, \n\tvintage_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\trun_id UUID NOT NULL, \n\tpublication_batch_id UUID, \n\tupdated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (source_series_id, period_start), \n\tFOREIGN KEY(source_series_id) REFERENCES source.source_series (id), \n\tFOREIGN KEY(run_id) REFERENCES ingestion.run (id), \n\tFOREIGN KEY(publication_batch_id) REFERENCES ingestion.publication_batch (id) ON DELETE SET NULL\n)',
    'CREATE TABLE data.observation_vintage (\n\tsource_series_id BIGINT NOT NULL, \n\tperiod_start DATE NOT NULL, \n\tperiod_end DATE NOT NULL, \n\tvalue NUMERIC(30, 10), \n\tvalue_text TEXT, \n\tobservation_status VARCHAR(32) NOT NULL, \n\tpublished_at TIMESTAMP WITH TIME ZONE, \n\tvintage_at TIMESTAMP WITH TIME ZONE NOT NULL, \n\tsource_updated_at TIMESTAMP WITH TIME ZONE, \n\trun_id UUID NOT NULL, \n\tpublication_batch_id UUID, \n\traw_object_id UUID, \n\tquality_flags JSONB NOT NULL, \n\tingested_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, \n\tPRIMARY KEY (source_series_id, period_start, vintage_at), \n\tFOREIGN KEY(source_series_id) REFERENCES source.source_series (id), \n\tFOREIGN KEY(run_id) REFERENCES ingestion.run (id), \n\tFOREIGN KEY(publication_batch_id) REFERENCES ingestion.publication_batch (id) ON DELETE SET NULL, \n\tFOREIGN KEY(raw_object_id) REFERENCES ingestion.raw_object (id)\n)',
    'CREATE INDEX observation_history_idx ON data.observation_vintage (source_series_id, period_start)',
]

DROP_STATEMENTS = [
    'DROP TABLE IF EXISTS data.observation_vintage CASCADE',
    'DROP TABLE IF EXISTS data.observation_latest CASCADE',
    'DROP TABLE IF EXISTS app.ai_citation CASCADE',
    'DROP TABLE IF EXISTS ingestion.quality_result CASCADE',
    'DROP TABLE IF EXISTS ingestion.publication_batch CASCADE',
    'DROP TABLE IF EXISTS docs.chunk CASCADE',
    'DROP TABLE IF EXISTS app.report CASCADE',
    'DROP TABLE IF EXISTS app.ai_context CASCADE',
    'DROP TABLE IF EXISTS release.market_reaction CASCADE',
    'DROP TABLE IF EXISTS release.forecast_snapshot CASCADE',
    'DROP TABLE IF EXISTS release.event_series CASCADE',
    'DROP TABLE IF EXISTS ingestion.run CASCADE',
    'DROP TABLE IF EXISTS docs.document_version CASCADE',
    'DROP TABLE IF EXISTS app.project_share_link CASCADE',
    'DROP TABLE IF EXISTS app.project_item CASCADE',
    'DROP TABLE IF EXISTS app.notification CASCADE',
    'DROP TABLE IF EXISTS app.note CASCADE',
    'DROP TABLE IF EXISTS app.ai_run CASCADE',
    'DROP TABLE IF EXISTS source.source_series CASCADE',
    'DROP TABLE IF EXISTS source.license_policy CASCADE',
    'DROP TABLE IF EXISTS release.event CASCADE',
    'DROP TABLE IF EXISTS ingestion.raw_object CASCADE',
    'DROP TABLE IF EXISTS docs.document_series CASCADE',
    'DROP TABLE IF EXISTS app.saved_view CASCADE',
    'DROP TABLE IF EXISTS app.project CASCADE',
    'DROP TABLE IF EXISTS app.favorite CASCADE',
    'DROP TABLE IF EXISTS app.alert_rule CASCADE',
    'DROP TABLE IF EXISTS source.dataset CASCADE',
    'DROP TABLE IF EXISTS release.definition CASCADE',
    'DROP TABLE IF EXISTS fomc.projection CASCADE',
    'DROP TABLE IF EXISTS fomc.probability_snapshot CASCADE',
    'DROP TABLE IF EXISTS fomc.dot CASCADE',
    'DROP TABLE IF EXISTS docs.document CASCADE',
    'DROP TABLE IF EXISTS data.series_dependency CASCADE',
    'DROP TABLE IF EXISTS data.derived_definition CASCADE',
    'DROP TABLE IF EXISTS catalog.taxonomy_series CASCADE',
    'DROP TABLE IF EXISTS catalog.series_alias CASCADE',
    'DROP TABLE IF EXISTS app.workspace CASCADE',
    'DROP TABLE IF EXISTS app.refresh_session CASCADE',
    'DROP TABLE IF EXISTS source.provider CASCADE',
    'DROP TABLE IF EXISTS fomc.meeting CASCADE',
    'DROP TABLE IF EXISTS catalog.taxonomy_node CASCADE',
    'DROP TABLE IF EXISTS catalog.series CASCADE',
    'DROP TABLE IF EXISTS audit.audit_log CASCADE',
    'DROP TABLE IF EXISTS app.user_account CASCADE',
    'DROP TABLE IF EXISTS app.job CASCADE',
]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    for schema in SCHEMAS:
        op.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    for statement in CREATE_STATEMENTS:
        op.execute(statement)
    op.execute(
        """
        CREATE OR REPLACE VIEW data.canonical_observation_latest AS
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
        WHERE ss.is_primary AND ss.mapping_status = 'verified'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS document_chunk_embedding_hnsw_idx
        ON docs.chunk USING hnsw (embedding vector_cosine_ops)
        WHERE embedding IS NOT NULL
        """
    )
    op.execute(
        """
        COMMENT ON TABLE data.observation_vintage IS
        'Append-only observations. Insert a new vintage and refresh observation_latest; never rewrite history.'
        """
    )


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS data.canonical_observation_latest")
    for statement in DROP_STATEMENTS:
        op.execute(statement)
    for schema in reversed(SCHEMAS):
        op.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
