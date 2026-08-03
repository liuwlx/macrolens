export type RequestOptions = RequestInit & { idempotencyKey?: string };

export class MacroLensApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code?: string,
    public readonly requestId?: string,
  ) {
    super(message);
    this.name = "MacroLensApiError";
  }
}

export type ObservationQuery = {
  start?: string;
  end?: string;
  transform?: "level" | "difference" | "mom" | "qoq" | "yoy" | "annualized_3m" | "annualized_6m" | "rebased_100" | "zscore";
  vintage?: "latest" | "first_release" | string;
  include_lineage?: boolean;
};

export type Transform = NonNullable<ObservationQuery["transform"]>;
export type BrowserSort = "taxonomy" | "name" | "current_period" | "current" | "change" | "period_change" | "yoy";
export type BrowserOrder = "asc" | "desc";

export type LicenseInfo = {
  display_allowed: boolean;
  download_allowed: boolean;
  api_redistribution_allowed: boolean;
  ai_context_allowed: boolean;
  attribution_required: boolean;
  attribution_text: string | null;
};

export type ProviderInfo = {
  code: string;
  name: string;
  attribution: string | null;
  license_class: string;
};

export type SeriesSummary = {
  id: string;
  canonical_code: string;
  name_zh: string;
  name_en: string | null;
  theme: string;
  frequency: string;
  unit_code: string;
  unit_label_zh: string;
  default_transform: string;
  latest_period: string | null;
  latest_value: string | null;
  latest_vintage_at: string | null;
  provider: ProviderInfo | null;
};

export type BrowserObservation = {
  period_start: string;
  period_end: string;
  value: string | null;
  published_at: string | null;
  vintage_at: string;
};

export type BrowserMetric = {
  value: string | null;
  unit: string;
  status: "available" | "unavailable";
  basis: string | null;
  reason_code: string | null;
  reason: string | null;
};

export type BrowserFacetValue = { value: string; label: string; count: number };
export type BrowserFacets = Record<
  "provider" | "theme" | "frequency" | "unit" | "seasonal_adjustment",
  BrowserFacetValue[]
>;

export type SeriesBrowserItem = {
  series: SeriesSummary;
  current: BrowserObservation | null;
  previous: BrowserObservation | null;
  change: BrowserMetric;
  period_change: BrowserMetric;
  yoy: BrowserMetric;
  license: LicenseInfo | null;
  display_denied: boolean;
  source_status: "ready" | "missing" | "conflict";
  unavailable_reason_code: string | null;
  taxonomy_order: number;
};

export type SeriesBrowserResponse = {
  items: SeriesBrowserItem[];
  facets: BrowserFacets;
  pagination: { total: number; limit: number; offset: number };
  data_as_of: string;
};

export type SeriesBrowserQuery = {
  q?: string;
  node_id?: string;
  tree_code?: string;
  provider?: string;
  theme?: string;
  frequency?: string;
  unit?: string;
  seasonal_adjustment?: string;
  published_from?: string;
  published_to?: string;
  sort?: BrowserSort;
  order?: BrowserOrder;
  limit?: number;
  offset?: number;
  data_as_of?: string;
};

export type TaxonomyChildrenQuery = Omit<SeriesBrowserQuery, "node_id" | "tree_code" | "sort" | "order" | "limit" | "offset" | "data_as_of" | "published_from" | "published_to"> & {
  parent_id?: string;
  scope?: "children" | "all";
};

export type TaxonomyChildNode = {
  id: string;
  code: string;
  name_zh: string;
  name_en: string | null;
  node_type: string;
  icon_key: string | null;
  has_children: boolean;
  direct_series_count: number;
  descendant_series_count: number;
};

export type TaxonomyChildrenResponse = {
  tree_code: string;
  parent_id: string | null;
  nodes: TaxonomyChildNode[];
  series: SeriesSummary[];
};

export type CapabilityStatus = { allowed: boolean; reason_code: string | null; reason: string | null };
export type SeriesCapabilities = Record<
  "display" | "download" | "ai" | "trend" | "history" | "revisions" | "documents" | "contributions",
  CapabilityStatus
>;

export type SeriesAnalyticsResponse = {
  series: SeriesSummary;
  statistics: {
    count: number;
    mean: string | null;
    median: string | null;
    min: string | null;
    max: string | null;
    stddev: string | null;
    current_percentile: string | null;
  };
  next_release: {
    id: string;
    title_zh: string;
    title_en: string | null;
    scheduled_at: string;
    source_timezone: string;
    status: string;
    role: string;
  } | null;
  contributions: {
    available: boolean;
    reason_code: string | null;
    reason: string | null;
    target_unit: string | null;
    periods: Array<Record<string, unknown>>;
    components: Array<Record<string, unknown>>;
    reconciliation: Record<string, string | boolean>;
  };
  capabilities: SeriesCapabilities;
  data_as_of: string;
};

export type SeriesAnalyticsQuery = {
  start?: string;
  end?: string;
  transform?: Transform;
  data_as_of?: string;
};

export type AICapabilityResponse = {
  series_id: string;
  configured: boolean;
  allowed: boolean;
  reason_code: string | null;
  reason: string | null;
};

export type AIContextInput = {
  context_type: "series" | "document" | "release_event" | "fomc_meeting" | "saved_view" | "note";
  context_id: string;
};

export type AIRunCreate = {
  prompt: string;
  mode?: "quick" | "deep_research" | "scenario";
  project_id?: string;
  data_as_of?: string;
  contexts: AIContextInput[];
};

function withQuery<T extends object>(path: string, query: T): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined) params.set(key, String(value));
  }
  return `${path}${params.size ? `?${params}` : ""}`;
}

export class MacroLensClient {
  constructor(
    public readonly baseUrl: string,
    private readonly fetcher: typeof fetch = fetch,
  ) {}

  private async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
    if (options.idempotencyKey) headers.set("Idempotency-Key", options.idempotencyKey);
    const response = await this.fetcher(`${this.baseUrl.replace(/\/$/, "")}${path}`, {
      ...options,
      headers,
      credentials: "include",
    });
    if (response.status === 204) return undefined as T;
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new MacroLensApiError(
        payload.detail ?? payload.message ?? `HTTP ${response.status}`,
        response.status,
        payload.code,
        response.headers.get("x-request-id") ?? undefined,
      );
    }
    return payload as T;
  }

  private async requestBlob(path: string): Promise<Blob> {
    const response = await this.fetcher(`${this.baseUrl.replace(/\/$/, "")}${path}`, {
      credentials: "include",
      headers: { Accept: "text/csv" },
    });
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => ({}));
      const problem = typeof payload === "object" && payload !== null ? payload as Record<string, unknown> : {};
      throw new MacroLensApiError(
        typeof problem.detail === "string" ? problem.detail : `HTTP ${response.status}`,
        response.status,
        typeof problem.code === "string" ? problem.code : undefined,
        response.headers.get("x-request-id") ?? undefined,
      );
    }
    return response.blob();
  }

  health<T = unknown>() { return this.request<T>("/health"); }
  series<T = unknown>(query = "") { return this.request<T>(`/series${query}`); }
  seriesDetail<T = unknown>(seriesId: string) { return this.request<T>(`/series/${seriesId}`); }
  observations<T = unknown>(seriesId: string, query: ObservationQuery = {}) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) if (value !== undefined) params.set(key, String(value));
    return this.request<T>(`/series/${seriesId}/observations${params.size ? `?${params}` : ""}`);
  }
  taxonomyChildren(treeCode: string, query: TaxonomyChildrenQuery = {}) {
    return this.request<TaxonomyChildrenResponse>(withQuery(`/taxonomies/${encodeURIComponent(treeCode)}/children`, query));
  }
  seriesBrowser(query: SeriesBrowserQuery = {}) {
    return this.request<SeriesBrowserResponse>(withQuery("/series/browser", query));
  }
  exportSeriesBrowser(query: Omit<SeriesBrowserQuery, "limit" | "offset"> = {}) {
    return this.requestBlob(withQuery("/series/browser/export", query));
  }
  seriesAnalytics(seriesId: string, query: SeriesAnalyticsQuery = {}) {
    return this.request<SeriesAnalyticsResponse>(withQuery(`/series/${seriesId}/analytics`, query));
  }
  exportSeries(seriesId: string, query: SeriesAnalyticsQuery = {}) {
    return this.requestBlob(withQuery(`/series/${seriesId}/export`, query));
  }
  aiCapabilities(seriesId: string) {
    return this.request<AICapabilityResponse>(withQuery("/ai/capabilities", { series_id: seriesId }));
  }
  revisions<T = unknown>(seriesId: string) { return this.request<T>(`/series/${seriesId}/revisions`); }
  releaseEvents<T = unknown>(query = "") { return this.request<T>(`/release-events${query}`); }
  releaseEvent<T = unknown>(eventId: string) { return this.request<T>(`/release-events/${eventId}`); }
  fomcMeetings<T = unknown>(query = "") { return this.request<T>(`/fomc/meetings${query}`); }
  documents<T = unknown>(query = "") { return this.request<T>(`/documents${query}`); }
  document<T = unknown>(documentId: string) { return this.request<T>(`/documents/${documentId}`); }
  compare<T = unknown>(payload: unknown) {
    return this.request<T>("/compare/query", { method: "POST", body: JSON.stringify(payload) });
  }
  createAiRun<T = unknown>(payload: AIRunCreate, idempotencyKey?: string) {
    return this.request<T>("/ai/runs", { method: "POST", body: JSON.stringify(payload), idempotencyKey });
  }
  aiRun<T = unknown>(runId: string) { return this.request<T>(`/ai/runs/${runId}`); }
  projects<T = unknown>() { return this.request<T>("/me/projects"); }
  savedViews<T = unknown>() { return this.request<T>("/me/saved-views"); }
  reports<T = unknown>() { return this.request<T>("/me/reports"); }
}
