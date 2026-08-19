import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SeriesBrowserResponse } from "@/lib/types";

import { BrowserTable } from "./browser-table";
import { defaultBrowserState } from "./browser-query";

const response: SeriesBrowserResponse = {
  data_mode: "live",
  items: [{
    series: { id: "series-1", canonical_code: "PCE_CORE", name_zh: "核心PCE", theme: "通胀", frequency: "monthly", unit_code: "percent", unit_label_zh: "%", default_transform: "yoy", provider: { code: "BEA", name: "BEA", license_class: "open" } },
    current: { period_start: "2024-06-01", value: 2.6 },
    previous: { period_start: "2024-05-01", value: 2.8 },
    change: { value: -0.2, unit: "pp", status: "available" },
    period_change: { value: -0.71, unit: "%", basis: "mom", status: "available" },
    yoy: { value: 3.63, unit: "%", basis: "yoy", status: "available" },
    display_denied: false,
    availability: "available",
  }],
  facets: { provider: [], theme: [], frequency: [], unit: [], seasonal_adjustment: [] },
  pagination: { total: 1, limit: 20, offset: 0 },
  data_as_of: "2026-08-04T00:00:00Z",
};

describe("BrowserTable", () => {
  it("supports keyboard row selection and sortable headers", () => {
    const select = vi.fn();
    const sort = vi.fn();
    render(<BrowserTable state={defaultBrowserState} data={response} isLoading={false} isFetching={false} onRetry={vi.fn()} onRefresh={vi.fn()} onExport={vi.fn()} onSelect={select} onSort={sort} onPage={vi.fn()} />);
    const row = screen.getByText("核心PCE").closest("tr");
    expect(row).toHaveAttribute("tabindex", "0");
    fireEvent.keyDown(row!, { key: "Enter" });
    expect(select).toHaveBeenCalledWith(response.items[0]);
    fireEvent.click(screen.getByRole("button", { name: "同比" }));
    expect(sort).toHaveBeenCalledWith("yoy");
  });

  it("shows missing metrics as unavailable rather than zero", () => {
    const unavailable = { ...response, items: [{ ...response.items[0], change: { value: null, status: "unavailable" as const, reason: "历史不足" } }] };
    render(<BrowserTable state={defaultBrowserState} data={unavailable} isLoading={false} isFetching={false} onRetry={vi.fn()} onRefresh={vi.fn()} onExport={vi.fn()} onSelect={vi.fn()} onSort={vi.fn()} onPage={vi.fn()} />);
    expect(screen.getByTitle("历史不足")).toHaveTextContent("—");
  });

  it("renders not-ingested catalog series as a normal availability state", () => {
    const notIngested: SeriesBrowserResponse = {
      ...response,
      items: [{
        ...response.items[0],
        availability: "not_ingested",
        current: null,
        previous: null,
      }],
    };
    render(<BrowserTable state={defaultBrowserState} data={notIngested} isLoading={false} isFetching={false} onRetry={vi.fn()} onRefresh={vi.fn()} onExport={vi.fn()} onSelect={vi.fn()} onSort={vi.fn()} onPage={vi.fn()} />);
    expect(screen.getByText("尚未采集")).toBeVisible();
    expect(screen.queryByText("明细表加载失败")).not.toBeInTheDocument();
  });

  it.each([
    ["pending_mapping", "待映射"],
    ["pending_credentials", "待凭据"],
    ["pending_license", "待许可"],
    ["not_available_for_geography", "美国无此序列"],
  ] as const)("renders %s as an explicit catalog state", (availability, label) => {
    const pending: SeriesBrowserResponse = {
      ...response,
      items: [{
        ...response.items[0],
        availability,
        current: null,
        previous: null,
      }],
    };
    render(<BrowserTable state={defaultBrowserState} data={pending} isLoading={false} isFetching={false} onRetry={vi.fn()} onRefresh={vi.fn()} onExport={vi.fn()} onSelect={vi.fn()} onSort={vi.fn()} onPage={vi.fn()} />);
    expect(screen.getByText(label)).toBeVisible();
  });
});
