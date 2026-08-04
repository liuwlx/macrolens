import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { TaxonomyChildrenResponse } from "@/lib/types";

import { defaultBrowserState } from "./browser-query";
import { MetricTree } from "./metric-tree";

const apiFetch = vi.fn();
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiFetch: (...args: unknown[]) => apiFetch(...args),
}));

afterEach(() => {
  cleanup();
  apiFetch.mockReset();
});

describe("MetricTree", () => {
  it("renders an ARIA tree and selects taxonomy nodes", async () => {
    apiFetch.mockResolvedValue({ data_mode: "live", tree_code: "macro-default", parent_id: null, nodes: [{ id: "prices", code: "prices", name_zh: "通胀", node_type: "group", has_children: true, direct_series_count: 2, descendant_series_count: 24 }], series: [] } satisfies TaxonomyChildrenResponse);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const onNode = vi.fn();
    render(<QueryClientProvider client={client}><MetricTree state={defaultBrowserState} onNode={onNode} onSeries={vi.fn()} /></QueryClientProvider>);
    const item = await screen.findByRole("treeitem", { name: /通胀/ });
    expect(screen.getByRole("tree", { name: "宏观指标树" })).toBeInTheDocument();
    fireEvent.click(item);
    expect(onNode).toHaveBeenCalledWith("prices");
    expect(item).toHaveAttribute("aria-expanded", "true");
  });

  it("expands a leaf taxonomy node that owns direct series", async () => {
    apiFetch.mockImplementation((path: string) => {
      if (path.includes("parent_id=prices")) {
        return Promise.resolve({
          data_mode: "live",
          tree_code: "macro-default",
          parent_id: "prices",
          nodes: [],
          series: [{
            id: "cpi",
            canonical_code: "US.CPI",
            name_zh: "居民消费价格指数",
            frequency: "monthly",
            unit_code: "index",
            unit_label_zh: "指数",
          }],
        } satisfies TaxonomyChildrenResponse);
      }
      return Promise.resolve({
        data_mode: "live",
        tree_code: "macro-default",
        parent_id: null,
        nodes: [{
          id: "prices",
          code: "prices",
          name_zh: "通胀",
          node_type: "group",
          has_children: false,
          direct_series_count: 1,
          descendant_series_count: 1,
        }],
        series: [],
      } satisfies TaxonomyChildrenResponse);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MetricTree state={defaultBrowserState} onNode={vi.fn()} onSeries={vi.fn()} />
      </QueryClientProvider>,
    );

    const leaf = await screen.findByRole("treeitem", { name: /通胀/ });
    expect(leaf).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(leaf);

    expect(await screen.findByRole("treeitem", { name: "居民消费价格指数" }))
      .toHaveAttribute("aria-level", "2");
    expect(leaf).toHaveAttribute("aria-expanded", "true");
    expect(apiFetch).toHaveBeenCalledWith(
      expect.stringContaining("parent_id=prices"),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });
});
