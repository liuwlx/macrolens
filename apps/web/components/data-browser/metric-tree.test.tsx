import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { TaxonomyChildrenResponse } from "@/lib/types";

import { defaultBrowserState } from "./browser-query";
import { MetricTree } from "./metric-tree";

const apiFetch = vi.fn();
vi.mock("@/lib/api", () => ({ apiFetch: (...args: unknown[]) => apiFetch(...args), queryString: () => "" }));

describe("MetricTree", () => {
  it("renders an ARIA tree and selects taxonomy nodes", async () => {
    apiFetch.mockResolvedValue({ tree_code: "macro-default", parent_id: null, nodes: [{ id: "prices", code: "prices", name_zh: "通胀", node_type: "group", has_children: true, direct_series_count: 2, descendant_series_count: 24 }], series: [] } satisfies TaxonomyChildrenResponse);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const onNode = vi.fn();
    render(<QueryClientProvider client={client}><MetricTree state={defaultBrowserState} onNode={onNode} onSeries={vi.fn()} /></QueryClientProvider>);
    const item = await screen.findByRole("treeitem", { name: /通胀/ });
    expect(screen.getByRole("tree", { name: "宏观指标树" })).toBeInTheDocument();
    fireEvent.click(item);
    expect(onNode).toHaveBeenCalledWith("prices");
    expect(item).toHaveAttribute("aria-expanded", "true");
  });
});
