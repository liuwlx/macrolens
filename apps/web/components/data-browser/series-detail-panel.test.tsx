import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SeriesBrowserItem } from "@/lib/types";

import { SeriesDetailPanel } from "./series-detail-panel";

const item: SeriesBrowserItem = {
  availability: "pending_mapping",
  series: {
    id: "series-pending",
    canonical_code: "US.PCE.HEADLINE",
    name_zh: "总PCE价格指数",
    theme: "通胀",
    frequency: "monthly",
    unit_code: "index",
    unit_label_zh: "指数",
    default_transform: "level",
    provider: { code: "BEA_API", name: "BEA", license_class: "public" },
  },
  current: null,
  previous: null,
  change: { value: null, status: "unavailable" },
  period_change: { value: null, status: "unavailable" },
  yoy: { value: null, status: "unavailable" },
  display_denied: false,
};

describe("SeriesDetailPanel catalog-only interactions", () => {
  it("shows readiness and fails closed for data-dependent actions", () => {
    render(<SeriesDetailPanel item={item} isLoading={false} isFavorite={false} favoritePending={false} onFavorite={vi.fn()} onHistory={vi.fn()} canSyncHistory={false} onSyncHistory={vi.fn()} historySyncPending={false} onCompare={vi.fn()} onExport={vi.fn()} onAI={vi.fn()} />);

    expect(screen.getByText("待映射")).toBeVisible();
    expect(screen.getByRole("button", { name: "查看历史数据" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "加入对比" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "导出数据" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "加入 AI 上下文" })).toBeDisabled();
  });

  it("offers history sync for an available TradingView series", () => {
    const sync = vi.fn();
    const tradingViewItem: SeriesBrowserItem = {
      ...item,
      availability: "available",
      series: {
        ...item.series,
        canonical_code: "US.TV.UNEMPLOYMENT.RATE",
        name_zh: "失业率",
        provider: { code: "TRADINGVIEW_WEB", name: "TradingView", license_class: "internal" },
      },
    };
    render(<SeriesDetailPanel item={tradingViewItem} isLoading={false} isFavorite={false} favoritePending={false} onFavorite={vi.fn()} onHistory={vi.fn()} canSyncHistory onSyncHistory={sync} historySyncPending={false} onCompare={vi.fn()} onExport={vi.fn()} onAI={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "同步历史数据" }));
    expect(sync).toHaveBeenCalledOnce();
  });
});
