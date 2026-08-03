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

  health<T = unknown>() { return this.request<T>("/health"); }
  series<T = unknown>(query = "") { return this.request<T>(`/series${query}`); }
  seriesDetail<T = unknown>(seriesId: string) { return this.request<T>(`/series/${seriesId}`); }
  observations<T = unknown>(seriesId: string, query: ObservationQuery = {}) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) if (value !== undefined) params.set(key, String(value));
    return this.request<T>(`/series/${seriesId}/observations${params.size ? `?${params}` : ""}`);
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
  createAiRun<T = unknown>(payload: unknown, idempotencyKey?: string) {
    return this.request<T>("/ai/runs", { method: "POST", body: JSON.stringify(payload), idempotencyKey });
  }
  aiRun<T = unknown>(runId: string) { return this.request<T>(`/ai/runs/${runId}`); }
  projects<T = unknown>() { return this.request<T>("/me/projects"); }
  savedViews<T = unknown>() { return this.request<T>("/me/saved-views"); }
  reports<T = unknown>() { return this.request<T>("/me/reports"); }
}
