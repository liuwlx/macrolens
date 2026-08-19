export type User = {
  id: string;
  email: string;
  display_name: string;
  role: string;
};

export type JobPublic = {
  id: string;
  job_type: string;
  status: string;
  priority: number;
  payload: Record<string, unknown>;
  attempts: number;
  max_attempts: number;
  last_error?: string | null;
  result: Record<string, unknown>;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type HistoryBatchStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "partial_failure"
  | "failed"
  | "empty";

export type HistoryBatchPublic = {
  batch_id: string;
  status: HistoryBatchStatus;
  total: number;
  candidate_count: number;
  skipped_completed: number;
  queued: number;
  running: number;
  succeeded: number;
  failed: number;
  inserted: number;
  revised: number;
  unchanged: number;
  staged_observation_count: number;
  failures: unknown[];
};

export type ProviderInfo = {
  code: string;
  name: string;
  attribution?: string | null;
  license_class: string;
};

export type LicenseInfo = {
  display_allowed: boolean;
  download_allowed: boolean;
  api_redistribution_allowed: boolean;
  ai_context_allowed: boolean;
  attribution_required: boolean;
  attribution_text?: string | null;
};

export type DataMode = "live" | "demo";

export type SeriesSummary = {
  id: string;
  canonical_code: string;
  name_zh: string;
  name_en?: string | null;
  theme: string;
  frequency: string;
  unit_code: string;
  unit_label_zh: string;
  default_transform: string;
  latest_period?: string | null;
  latest_value?: string | number | null;
  latest_vintage_at?: string | null;
  provider?: ProviderInfo | null;
};

export type SeriesDetail = SeriesSummary & {
  description?: string | null;
  seasonal_adjustment: string;
  geography_code: string;
  decimal_places: number;
  status: string;
  first_period?: string | null;
  aliases: string[];
};

export type ObservationPoint = {
  period_start: string;
  period_end: string;
  value: number | string | null;
  value_text?: string | null;
  status: string;
  published_at?: string | null;
  vintage_at: string;
  source_series_id?: number | null;
  run_id?: string | null;
  publication_batch_id?: string | null;
  raw_object_id?: string | null;
};

export type SeriesLineage = {
  provider: string;
  dataset: string;
  provider_series_id?: string | null;
  source_series_id: number;
  source_locator: Record<string, unknown>;
};

export type ObservationResponse = {
  series: SeriesSummary;
  data: ObservationPoint[];
  meta: {
    data_mode: DataMode;
    data_as_of: string;
    vintage: string;
    transform: string;
    frequency: string;
    unit: string;
    lineage?: SeriesLineage | null;
    license?: LicenseInfo | null;
  };
};

export type ReleaseEvent = {
  id: string;
  title_zh: string;
  title_en?: string | null;
  country_code: string;
  reference_period?: string | null;
  scheduled_at: string;
  actual_released_at?: string | null;
  status: string;
  importance_score?: number | null;
  release_type: string;
  provider_code: string;
  provider_name: string;
  official_url?: string | null;
  consensus_value?: number | string | null;
  metrics: Array<{
    series_id: string;
    name_zh: string;
    transform: string;
    actual_value?: number | string | null;
    previous_value?: number | string | null;
    revised_previous_value?: number | string | null;
    unit_label?: string | null;
  }>;
};

export type FomcMeeting = {
  id: string;
  meeting_start: string;
  meeting_end: string;
  decision_at?: string | null;
  status: string;
  target_rate_lower?: number | string | null;
  target_rate_upper?: number | string | null;
  decision_code?: string | null;
  statement_tone?: string | null;
  summary_zh?: string | null;
  official_url?: string | null;
};

export type DocumentSummary = {
  id: string;
  title: string;
  title_zh?: string | null;
  document_type: string;
  provider_code: string;
  provider_name: string;
  source_url: string;
  published_at?: string | null;
  language: string;
  copyright_status: string;
  status: string;
  summary_zh?: string | null;
  related_series: SeriesSummary[];
  license?: LicenseInfo | null;
};

export type Project = {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
};

export type Favorite = {
  id: string;
  object_type: string;
  object_id: string;
  group_name?: string | null;
  note?: string | null;
  sort_order: number;
  created_at: string;
};

export type SavedView = {
  id: string;
  name: string;
  view_type: string;
  definition: {
    series?: Array<{
      series: SeriesSummary;
      transform: string;
      axis: "left" | "right";
      lag_periods: number;
    }>;
    start?: string;
    end?: string;
  } & Record<string, unknown>;
  description?: string | null;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
};

export type AlertRule = {
  id: string;
  name: string;
  alert_type: string;
  target_type?: string | null;
  target_id?: string | null;
  rule: Record<string, unknown>;
  channels: string[];
  active: boolean;
  last_evaluated_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type Notification = {
  id: string;
  notification_type: string;
  title: string;
  body?: string | null;
  action_url?: string | null;
  payload: Record<string, unknown>;
  created_at: string;
  read_at?: string | null;
};

export type AIRun = {
  id: string;
  prompt: string;
  mode: string;
  model_name: string;
  model_version?: string | null;
  prompt_version: string;
  data_as_of: string;
  status: string;
  result_markdown?: string | null;
  assumptions: unknown[];
  error_message?: string | null;
  token_usage: Record<string, unknown>;
  estimated_cost_usd?: number | string | null;
  created_at: string;
  completed_at?: string | null;
};

export type ReleaseEventDetail = ReleaseEvent & {
  source_timezone: string;
  forecasts: Array<{
    observed_at: string;
    consensus_value?: number | string | null;
    median_value?: number | string | null;
    high_value?: number | string | null;
    low_value?: number | string | null;
    respondent_count?: number | null;
    provider_code: string;
  }>;
  market_reactions: Array<{
    instrument_code: string;
    window_code: string;
    absolute_change?: number | string | null;
    percent_change?: number | string | null;
    observed_at: string;
  }>;
};


export type FomcProbability = {
  observed_at: string;
  target_lower: number | string;
  target_upper: number | string;
  probability: number | string;
  provider_code: string;
};

export type FomcMeetingDetail = FomcMeeting & {
  press_conference_tone?: string | null;
  projections: Array<{
    variable_code: string;
    horizon: string;
    statistic: string;
    value?: number | string | null;
    unit: string;
  }>;
  dots: Array<{ horizon: string; dot_value: number | string; dot_count: number }>;
  documents: DocumentSummary[];
};

export type DocumentDetail = DocumentSummary & {
  latest_version_id?: string | null;
  version_no?: number | null;
  content_hash?: string | null;
  extracted_text?: string | null;
  translated_text_zh?: string | null;
  chunks: Array<{
    id: string;
    chunk_no: number;
    page_start?: number | null;
    page_end?: number | null;
    heading_path?: string | null;
    content: string;
  }>;
};

export type CompareResponse = {
  items: Array<{
    series: SeriesSummary;
    transform: string;
    axis: string;
    lag_periods: number;
    data: ObservationPoint[];
    license?: LicenseInfo | null;
  }>;
  correlations: Array<{
    left_series_id: string;
    right_series_id: string;
    coefficient?: number | null;
    observations: number;
  }>;
  data_as_of: string;
};

export type AICitation = {
  id: string;
  citation_no: number;
  document_chunk_id?: string | null;
  series_id?: string | null;
  period_start?: string | null;
  vintage_at?: string | null;
  quote_text?: string | null;
  locator: Record<string, unknown>;
};

export type ProjectItem = {
  id: string;
  project_id: string;
  object_type: string;
  object_id: string;
  title_override?: string | null;
  sort_order: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
};

export type Note = {
  id: string;
  project_id?: string | null;
  author_user_id: string;
  title?: string | null;
  body_markdown: string;
  version_no: number;
  created_at: string;
  updated_at: string;
};

export type ProjectDetail = Project & { items: ProjectItem[]; notes: Note[] };

export type ProjectShare = {
  id: string;
  project_id: string;
  share_url?: string | null;
  expires_at: string;
  revoked_at?: string | null;
  created_at: string;
};

export type Report = {
  id: string;
  project_id?: string | null;
  ai_run_id?: string | null;
  title: string;
  content_markdown: string;
  status: string;
  version_no: number;
  metadata_json: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type ProblemDetails = {
  type?: string;
  title?: string;
  status: number;
  detail?: string;
  instance?: string;
  code?: string;
  errors?: Record<string, string[]>;
};

export type TaxonomyBrowserNode = {
  id: string;
  code: string;
  name_zh: string;
  name_en?: string | null;
  node_type: string;
  icon_key?: string | null;
  has_children: boolean;
  direct_series_count: number;
  descendant_series_count: number;
};

export type TaxonomyBrowserSeries = Pick<
  SeriesSummary,
  "id" | "canonical_code" | "name_zh" | "name_en" | "frequency" | "unit_code" | "unit_label_zh"
>;

export type TaxonomyChildrenResponse = {
  data_mode: DataMode;
  tree_code: string;
  parent_id: string | null;
  nodes: TaxonomyBrowserNode[];
  series: TaxonomyBrowserSeries[];
};

export type BrowserMetricStatus = "available" | "unavailable" | "restricted";
export type BrowserSeriesAvailability =
  | "available"
  | "pending_mapping"
  | "pending_credentials"
  | "pending_license"
  | "not_ingested"
  | "not_available_as_of"
  | "not_available_for_geography";

export type BrowserMetricValue = {
  value: number | string | null;
  unit?: string | null;
  status: BrowserMetricStatus;
  reason_code?: string | null;
  reason?: string | null;
  basis?: "daily" | "weekly" | "mom" | "qoq" | "yoy" | string | null;
};

export type BrowserObservation = {
  period_start: string;
  period_end?: string | null;
  value: number | string | null;
  published_at?: string | null;
  vintage_at?: string | null;
  source_series_id?: number | null;
  run_id?: string | null;
  publication_batch_id?: string | null;
  raw_object_id?: string | null;
};

export type SeriesBrowserItem = {
  availability: BrowserSeriesAvailability;
  series: SeriesSummary & {
    decimal_places?: number;
    seasonal_adjustment?: string;
    description?: string | null;
  };
  current: BrowserObservation | null;
  previous: BrowserObservation | null;
  change: BrowserMetricValue;
  period_change: BrowserMetricValue;
  yoy: BrowserMetricValue;
  license?: LicenseInfo | null;
  display_denied: boolean;
  source_status?: string | null;
  unavailable_reason_code?: string | null;
  taxonomy_order?: number | null;
};

export type BrowserFacetItem = {
  value: string;
  label: string;
  count: number;
};

export type SeriesBrowserFacets = {
  provider: BrowserFacetItem[];
  theme: BrowserFacetItem[];
  frequency: BrowserFacetItem[];
  unit: BrowserFacetItem[];
  seasonal_adjustment: BrowserFacetItem[];
};

export type SeriesBrowserResponse = {
  data_mode: DataMode;
  items: SeriesBrowserItem[];
  facets: SeriesBrowserFacets;
  pagination: { total: number; limit: number; offset: number };
  data_as_of: string;
};

export type AnalyticsCapability = {
  allowed: boolean;
  reason_code?: string | null;
  reason?: string | null;
};

export type SeriesAnalyticsCapabilities = {
  display: AnalyticsCapability;
  download: AnalyticsCapability;
  ai: AnalyticsCapability;
  trend: AnalyticsCapability;
  history: AnalyticsCapability;
  revisions: AnalyticsCapability;
  documents: AnalyticsCapability;
  contributions: AnalyticsCapability;
};

export type SeriesStatistics = {
  count: number;
  mean: number | null;
  median: number | null;
  min: number | null;
  max: number | null;
  stddev: number | null;
  current_percentile: number | null;
};

export type NextSeriesRelease = {
  id: string;
  title_zh: string;
  scheduled_at: string;
  source_timezone: string;
  status: string;
  role: "headline" | "component" | "reference" | string;
};

export type ContributionPeriod = {
  period_start: string;
  target_value?: number | null;
};

export type ContributionComponent = {
  series_id: string;
  name_zh: string;
  values: Array<number | null>;
};

export type ContributionAnalysis = {
  available: boolean;
  reason_code?: string | null;
  reason?: string | null;
  target_unit?: string | null;
  periods: ContributionPeriod[];
  components: ContributionComponent[];
  reconciliation?: {
    passed: boolean;
    tolerance?: number | null;
    difference?: number | null;
    reason?: string | null;
  } | null;
};

export type SeriesAnalyticsResponse = {
  data_mode: DataMode;
  statistics: SeriesStatistics;
  next_release: NextSeriesRelease | null;
  contributions: ContributionAnalysis;
  capabilities: SeriesAnalyticsCapabilities;
  lineage?: SeriesLineage | null;
  data_as_of: string;
};

export type AICapabilitiesResponse = {
  configured: boolean;
  allowed: boolean;
  reason_code?: string | null;
  reason?: string | null;
};

export type RevisionItem = {
  period_start: string;
  versions: number;
  latest_value?: number | string | null;
  previous_value?: number | string | null;
  absolute_revision?: number | string | null;
  first_run_id?: string | null;
  latest_run_id?: string | null;
  first_raw_object_id?: string | null;
  latest_raw_object_id?: string | null;
};

export type RevisionResponse = { items: RevisionItem[] };
