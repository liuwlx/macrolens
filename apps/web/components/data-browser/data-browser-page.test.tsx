import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { HistoryBatchPublic, SeriesBrowserResponse, TaxonomyChildrenResponse } from "@/lib/types";

import { DataBrowserPage } from "./data-browser-page";

const apiFetch = vi.fn();
const searchParams = new URLSearchParams("provider=TRADINGVIEW_WEB");
const authState = vi.hoisted(() => ({ role: "admin" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => searchParams,
}));

vi.mock("@/components/auth-provider", () => ({
  useAuth: () => ({
    user: { id: "user-1", email: "user@example.com", display_name: "User", role: authState.role },
  }),
}));

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}));

const browserResponse: SeriesBrowserResponse = {
  data_mode: "live",
  items: [],
  facets: { provider: [], theme: [], frequency: [], unit: [], seasonal_adjustment: [] },
  pagination: { total: 0, limit: 20, offset: 0 },
  data_as_of: "2026-08-20T00:00:00Z",
};

const taxonomyResponse: TaxonomyChildrenResponse = {
  data_mode: "live",
  tree_code: "macro-default",
  parent_id: null,
  nodes: [],
  series: [],
};

const emptyBatch: HistoryBatchPublic = {
  batch_id: "batch-1",
  status: "empty",
  total: 339,
  candidate_count: 0,
  skipped_completed: 339,
  queued: 0,
  running: 0,
  succeeded: 0,
  failed: 0,
  inserted: 0,
  revised: 0,
  unchanged: 0,
  staged_observation_count: 0,
  failures: [],
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const rendered = render(
    <QueryClientProvider client={client}>
      <DataBrowserPage />
    </QueryClientProvider>,
  );
  return { client, ...rendered };
}

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  apiFetch.mockReset();
  authState.role = "admin";
  searchParams.delete("series");
  searchParams.set("provider", "TRADINGVIEW_WEB");
});

describe("DataBrowserPage bulk TradingView history sync", () => {
  it("starts one provider history batch per click and reuses its idempotency key", async () => {
    apiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/series/browser")) return Promise.resolve(browserResponse);
      if (path.startsWith("/taxonomies/")) return Promise.resolve(taxonomyResponse);
      if (path === "/me/favorites") return Promise.resolve([]);
      if (path === "/admin/providers/TRADINGVIEW_WEB/history") return Promise.resolve(emptyBatch);
      throw new Error(`Unexpected API path: ${path}`);
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "批量同步历史" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(
      "/admin/providers/TRADINGVIEW_WEB/history",
      {
        method: "POST",
        body: expect.stringMatching(/^\{"idempotency_key":".+","limit":500\}$/),
        signal: expect.any(AbortSignal),
      },
    ));
    let posts = apiFetch.mock.calls.filter(([path]) => path === "/admin/providers/TRADINGVIEW_WEB/history");
    expect(posts).toHaveLength(1);

    await screen.findByText(/批量历史同步无需处理/);
    fireEvent.click(screen.getByRole("button", { name: "批量同步历史" }));
    await waitFor(() => {
      posts = apiFetch.mock.calls.filter(([path]) => path === "/admin/providers/TRADINGVIEW_WEB/history");
      expect(posts).toHaveLength(2);
    });
    expect(JSON.parse(String(posts[1][1]?.body)).idempotency_key)
      .toBe(JSON.parse(String(posts[0][1]?.body)).idempotency_key);
  });

  it("polls batch progress every two seconds and stops on a failed terminal response", async () => {
    const queuedBatch: HistoryBatchPublic = {
      ...emptyBatch,
      status: "queued",
      candidate_count: 339,
      skipped_completed: 0,
      queued: 339,
      succeeded: 0,
    };
    const runningBatch: HistoryBatchPublic = {
      ...queuedBatch,
      status: "running",
      queued: 300,
      running: 20,
      succeeded: 18,
      failed: 1,
      staged_observation_count: 1260,
    };
    const failedBatch: HistoryBatchPublic = {
      ...runningBatch,
      status: "failed",
      queued: 0,
      running: 0,
      succeeded: 330,
      failed: 9,
      staged_observation_count: 23840,
    };
    let batchReads = 0;
    apiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/series/browser")) return Promise.resolve(browserResponse);
      if (path.startsWith("/taxonomies/")) return Promise.resolve(taxonomyResponse);
      if (path === "/me/favorites") return Promise.resolve([]);
      if (path === "/admin/providers/TRADINGVIEW_WEB/history" && init?.method === "POST") {
        return Promise.resolve(queuedBatch);
      }
      if (path === "/admin/providers/TRADINGVIEW_WEB/history/batch-1") {
        batchReads += 1;
        return Promise.resolve(batchReads === 1 ? runningBatch : failedBatch);
      }
      throw new Error(`Unexpected API path: ${path}`);
    });
    const { client } = renderPage();
    const invalidate = vi.spyOn(client, "invalidateQueries");
    const button = await screen.findByRole("button", { name: "批量同步历史" });

    vi.useFakeTimers();
    fireEvent.click(button);
    await act(async () => {});
    expect(screen.getByRole("status")).toHaveTextContent("总数 339，排队 339，运行 0，成功 0，失败 0，历史点 0");

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(screen.getByRole("status")).toHaveTextContent("总数 339，排队 300，运行 20，成功 18，失败 1，历史点 1260");

    await act(async () => vi.advanceTimersByTimeAsync(2000));
    const terminalStatus = screen.getByRole("status");
    expect(terminalStatus).toHaveTextContent("批量历史同步失败");
    expect(terminalStatus).toHaveTextContent("总数 339，排队 0，运行 0，成功 330，失败 9，历史点 23840");
    expect(terminalStatus).toHaveClass("is-error");

    await act(async () => vi.advanceTimersByTimeAsync(10_000));
    expect(batchReads).toBe(2);
    expect(apiFetch.mock.calls.some(([path]) => String(path).startsWith("/admin/jobs"))).toBe(false);
    for (const queryKey of [
      "series-browser",
      "data-browser-detail",
      "data-browser-observations",
      "data-browser-analytics",
      "taxonomy-children",
    ]) {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: [queryKey] });
    }
  });

  it.each([
    ["demo mode", "admin", "demo"],
    ["non-admin user", "member", "live"],
  ])("hides the batch action for %s", async (_case, role, dataMode) => {
    authState.role = role;
    apiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/series/browser")) {
        return Promise.resolve({ ...browserResponse, data_mode: dataMode });
      }
      if (path.startsWith("/taxonomies/")) return Promise.resolve({ ...taxonomyResponse, data_mode: dataMode });
      if (path === "/me/favorites") return Promise.resolve([]);
      throw new Error(`Unexpected API path: ${path}`);
    });
    renderPage();

    await screen.findAllByText(/共 0 条/);
    expect(screen.queryByRole("button", { name: "批量同步历史" })).not.toBeInTheDocument();
  });

  it("hides the batch action outside a TradingView selection", async () => {
    searchParams.delete("provider");
    apiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/series/browser")) return Promise.resolve(browserResponse);
      if (path.startsWith("/taxonomies/")) return Promise.resolve(taxonomyResponse);
      if (path === "/me/favorites") return Promise.resolve([]);
      throw new Error(`Unexpected API path: ${path}`);
    });
    renderPage();

    await screen.findAllByText(/共 0 条/);
    expect(screen.queryByRole("button", { name: "批量同步历史" })).not.toBeInTheDocument();
  });

  it("shows the batch action for a selected TradingView indicator without a provider filter", async () => {
    searchParams.delete("provider");
    searchParams.set("series", "tv-series-1");
    const selectedBrowserResponse: SeriesBrowserResponse = {
      ...browserResponse,
      items: [{
        availability: "not_ingested",
        series: {
          id: "tv-series-1",
          canonical_code: "US.TV.CPI",
          name_zh: "美国消费者价格指数",
          theme: "通胀",
          frequency: "monthly",
          unit_code: "index",
          unit_label_zh: "指数",
          default_transform: "level",
          provider: { code: "TRADINGVIEW_WEB", name: "TradingView", license_class: "internal" },
        },
        current: null,
        previous: null,
        change: { value: null, status: "unavailable" },
        period_change: { value: null, status: "unavailable" },
        yoy: { value: null, status: "unavailable" },
        display_denied: false,
      }],
      pagination: { total: 1, limit: 20, offset: 0 },
    };
    apiFetch.mockImplementation((path: string) => {
      if (path.startsWith("/series/browser")) return Promise.resolve(selectedBrowserResponse);
      if (path.startsWith("/taxonomies/")) return Promise.resolve(taxonomyResponse);
      if (path === "/me/favorites") return Promise.resolve([]);
      throw new Error(`Unexpected API path: ${path}`);
    });
    renderPage();

    expect(await screen.findByRole("button", { name: "批量同步历史" })).toBeEnabled();
  });

  it("cancels pending polling when the page unmounts", async () => {
    const queuedBatch: HistoryBatchPublic = {
      ...emptyBatch,
      status: "queued",
      candidate_count: 339,
      skipped_completed: 0,
      queued: 339,
      succeeded: 0,
    };
    let batchReads = 0;
    apiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/series/browser")) return Promise.resolve(browserResponse);
      if (path.startsWith("/taxonomies/")) return Promise.resolve(taxonomyResponse);
      if (path === "/me/favorites") return Promise.resolve([]);
      if (path === "/admin/providers/TRADINGVIEW_WEB/history" && init?.method === "POST") {
        return Promise.resolve(queuedBatch);
      }
      if (path === "/admin/providers/TRADINGVIEW_WEB/history/batch-1") {
        batchReads += 1;
        return Promise.resolve(queuedBatch);
      }
      throw new Error(`Unexpected API path: ${path}`);
    });
    const { unmount } = renderPage();
    const button = await screen.findByRole("button", { name: "批量同步历史" });

    vi.useFakeTimers();
    fireEvent.click(button);
    await act(async () => {});
    unmount();
    await act(async () => vi.advanceTimersByTimeAsync(10_000));

    expect(batchReads).toBe(0);
  });

  it("aborts an in-flight batch read when the page unmounts", async () => {
    const queuedBatch: HistoryBatchPublic = {
      ...emptyBatch,
      status: "queued",
      candidate_count: 339,
      skipped_completed: 0,
      queued: 339,
    };
    let readSignal: AbortSignal | undefined;
    apiFetch.mockImplementation((path: string, init?: RequestInit) => {
      if (path.startsWith("/series/browser")) return Promise.resolve(browserResponse);
      if (path.startsWith("/taxonomies/")) return Promise.resolve(taxonomyResponse);
      if (path === "/me/favorites") return Promise.resolve([]);
      if (path === "/admin/providers/TRADINGVIEW_WEB/history" && init?.method === "POST") {
        return Promise.resolve(queuedBatch);
      }
      if (path === "/admin/providers/TRADINGVIEW_WEB/history/batch-1") {
        readSignal = init?.signal ?? undefined;
        return new Promise(() => {});
      }
      throw new Error(`Unexpected API path: ${path}`);
    });
    const { unmount } = renderPage();
    const button = await screen.findByRole("button", { name: "批量同步历史" });

    vi.useFakeTimers();
    fireEvent.click(button);
    await act(async () => {});
    await act(async () => vi.advanceTimersByTimeAsync(2000));
    expect(readSignal?.aborted).toBe(false);

    unmount();
    expect(readSignal?.aborted).toBe(true);
  });
});
