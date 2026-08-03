export const browserTabs = ["trend", "history", "revisions", "documents", "description"] as const;
export const browserSorts = ["taxonomy", "name", "current_period", "current", "change", "period_change", "yoy"] as const;

export type BrowserTab = (typeof browserTabs)[number];
export type BrowserSort = (typeof browserSorts)[number];
export type BrowserOrder = "asc" | "desc";

export type BrowserState = {
  q: string;
  series: string;
  node: string;
  provider: string;
  theme: string;
  frequency: string;
  unit: string;
  seasonal_adjustment: string;
  published_from: string;
  published_to: string;
  page: number;
  sort: BrowserSort;
  order: BrowserOrder;
  tab: BrowserTab;
  transform: string;
  start: string;
  end: string;
  data_as_of: string;
};

type SearchParamsReader = { get(name: string): string | null };

export const defaultBrowserState: BrowserState = {
  q: "",
  series: "",
  node: "",
  provider: "",
  theme: "",
  frequency: "",
  unit: "",
  seasonal_adjustment: "",
  published_from: "",
  published_to: "",
  page: 1,
  sort: "taxonomy",
  order: "asc",
  tab: "trend",
  transform: "level",
  start: "",
  end: "",
  data_as_of: "",
};

export function parseBrowserState(params: SearchParamsReader): BrowserState {
  const requestedPage = Number(params.get("page") ?? 1);
  const requestedSort = params.get("sort") ?? "taxonomy";
  const requestedOrder = params.get("order") ?? "asc";
  const requestedTab = params.get("tab") ?? "trend";
  return {
    q: params.get("q") ?? "",
    series: params.get("series") ?? "",
    node: params.get("node") ?? "",
    provider: params.get("provider") ?? "",
    theme: params.get("theme") ?? "",
    frequency: params.get("frequency") ?? "",
    unit: params.get("unit") ?? "",
    seasonal_adjustment: params.get("seasonal_adjustment") ?? "",
    published_from: params.get("published_from") ?? "",
    published_to: params.get("published_to") ?? "",
    page: Number.isFinite(requestedPage) && requestedPage >= 1 ? Math.floor(requestedPage) : 1,
    sort: browserSorts.includes(requestedSort as BrowserSort) ? (requestedSort as BrowserSort) : "taxonomy",
    order: requestedOrder === "desc" ? "desc" : "asc",
    tab: browserTabs.includes(requestedTab as BrowserTab) ? (requestedTab as BrowserTab) : "trend",
    transform: params.get("transform") ?? "level",
    start: params.get("start") ?? "",
    end: params.get("end") ?? "",
    data_as_of: params.get("data_as_of") ?? "",
  };
}

export function serializeBrowserState(state: BrowserState, preserved?: URLSearchParams): URLSearchParams {
  const params = new URLSearchParams(preserved?.toString());
  for (const key of Object.keys(defaultBrowserState) as Array<keyof BrowserState>) params.delete(key);
  for (const [key, value] of Object.entries(state)) {
    const defaultValue = defaultBrowserState[key as keyof BrowserState];
    if (value !== "" && value !== defaultValue) params.set(key, String(value));
  }
  return params;
}

export function patchBrowserState(state: BrowserState, patch: Partial<BrowserState>): BrowserState {
  const next = { ...state, ...patch };
  const filtering = ["q", "node", "provider", "theme", "frequency", "unit", "seasonal_adjustment", "published_from", "published_to"] as const;
  if (filtering.some((key) => patch[key] !== undefined && patch[key] !== state[key])) next.page = 1;
  return next;
}

export function resetBrowserFilters(state: BrowserState): BrowserState {
  return {
    ...state,
    q: "",
    node: "",
    provider: "",
    theme: "",
    frequency: "",
    unit: "",
    seasonal_adjustment: "",
    published_from: "",
    published_to: "",
    page: 1,
  };
}
