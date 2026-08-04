import { expect, test, type Page, type Route } from "@playwright/test";

const fixedSnapshot = "2026-08-04T00:00:00Z";

const item = {
  availability: "available",
  series: {
    id: "series-1",
    canonical_code: "CPI_TEST",
    name_zh: "居民消费价格指数",
    theme: "通胀",
    frequency: "monthly",
    unit_code: "percent",
    unit_label_zh: "%",
    default_transform: "yoy",
    decimal_places: 1,
    seasonal_adjustment: "NSA",
    provider: { code: "DEMO", name: "演示数据", license_class: "open" },
  },
  current: { period_start: "2026-06-01", value: 2.5 },
  previous: { period_start: "2026-05-01", value: 2.4 },
  change: { value: 0.1, unit: "pp", status: "available" },
  period_change: { value: 0.1, unit: "%", basis: "mom", status: "available" },
  yoy: { value: 2.5, unit: "%", basis: "yoy", status: "available" },
  display_denied: false,
  license: {
    display_allowed: true,
    download_allowed: true,
    api_redistribution_allowed: true,
    ai_context_allowed: true,
    attribution_required: false,
  },
};

const facets = { provider: [], theme: [], frequency: [], unit: [], seasonal_adjustment: [] };

async function fulfillApi(route: Route, mode: "live-empty" | "demo") {
  const url = new URL(route.request().url());
  const path = url.pathname;
  let body: unknown = {};
  if (path.endsWith("/auth/me")) {
    body = { id: "demo-user", email: "demo@example.test", display_name: "Demo", role: "admin" };
  } else if (path.endsWith("/series/browser/export")) {
    await route.fulfill({
      status: 200,
      contentType: "text/csv",
      headers: { "Content-Disposition": 'attachment; filename="macrolens-data-browser.csv"' },
      body: "canonical_code,data_mode\nCPI_TEST,DEMO\n",
    });
    return;
  } else if (path.endsWith("/series/browser")) {
    body = mode === "demo"
      ? { data_mode: "demo", items: [item], facets, pagination: { total: 1, limit: 20, offset: 0 }, data_as_of: fixedSnapshot }
      : { data_mode: "live", items: [{ ...item, availability: "not_ingested", current: null, previous: null }], facets, pagination: { total: 1, limit: 20, offset: 0 }, data_as_of: fixedSnapshot };
  } else if (path.endsWith("/taxonomies/macro-default/children")) {
    const parentId = url.searchParams.get("parent_id");
    const searching = url.searchParams.get("q") === "价格" && url.searchParams.get("scope") === "all";
    const nodes = !searching ? []
      : parentId === null ? [{ id: "macro", code: "macro", name_zh: "宏观经济", node_type: "group", has_children: true, direct_series_count: 0, descendant_series_count: 1 }]
        : parentId === "macro" ? [{ id: "prices", code: "prices", name_zh: "价格", node_type: "group", has_children: true, direct_series_count: 0, descendant_series_count: 1 }]
          : parentId === "prices" ? [{ id: "consumer-prices", code: "consumer-prices", name_zh: "居民价格", node_type: "group", has_children: false, direct_series_count: 1, descendant_series_count: 1 }]
            : [];
    body = { data_mode: mode === "demo" ? "demo" : "live", tree_code: "macro-default", parent_id: parentId, nodes, series: parentId === "consumer-prices" ? [item.series] : [] };
  } else if (path.endsWith("/me/favorites")) {
    body = [];
  } else if (path.endsWith("/series/series-1")) {
    body = { ...item.series, description: "演示指标", geography_code: "CN", status: "active", aliases: [] };
  } else if (path.endsWith("/series/series-1/analytics")) {
    body = {
      data_mode: mode === "demo" ? "demo" : "live",
      statistics: { count: 2, mean: 2.45, median: 2.45, min: 2.4, max: 2.5, stddev: 0.05, current_percentile: 100 },
      next_release: null,
      contributions: { available: false, periods: [], components: [] },
      capabilities: Object.fromEntries(["display", "download", "ai", "trend", "history", "revisions", "documents", "contributions"].map((key) => [key, { allowed: true }])),
      data_as_of: fixedSnapshot,
    };
  } else if (path.endsWith("/series/series-1/observations")) {
    body = { series: item.series, data: [], meta: { data_mode: mode === "demo" ? "demo" : "live", data_as_of: fixedSnapshot, vintage: "latest", transform: "yoy", frequency: "monthly", unit: "%" } };
  } else if (path.endsWith("/ai/capabilities")) {
    body = { configured: true, allowed: true };
  }
  await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
}

async function installApi(page: Page, mode: "live-empty" | "demo") {
  await page.route("**/api/v1/**", (route) => fulfillApi(route, mode));
}

test("not-ingested series is an empty data state and does not pin a snapshot", async ({ page }) => {
  await installApi(page, "live-empty");
  await page.goto("/data?view=v2");
  await expect(page.getByText("尚未采集")).toBeVisible();
  await expect(page).toHaveURL(/series=series-1/);
  expect(new URL(page.url()).searchParams.has("data_as_of")).toBe(false);
  await expect(page.getByText("明细表加载失败")).toHaveCount(0);
});

test("demo mode is persistent, read-only, snapshot-pinned, and exports marked CSV", async ({ page }) => {
  await installApi(page, "demo");
  await page.goto("/data?view=v2&data_as_of=2025-01-01T00%3A00%3A00Z");

  await expect(page.getByRole("note")).toContainText("DEMO");
  await expect(page).toHaveURL(new RegExp(`data_as_of=${encodeURIComponent(fixedSnapshot)}`));
  await expect(page.getByRole("button", { name: "收藏该指标" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "加入对比" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "加入 AI 上下文" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "查看历史数据" })).toBeEnabled();
  await expect(page.getByRole("tab", { name: "历史数据" })).toBeEnabled();
  await expect(page.getByRole("tab", { name: "修订历史" })).toBeEnabled();
  await expect(page.getByRole("heading", { name: "统计摘要" })).toBeVisible();

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "下载表格" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("macrolens-data-browser.demo.csv");
  const stream = await download.createReadStream();
  const chunks: Buffer[] = [];
  for await (const chunk of stream) chunks.push(Buffer.from(chunk));
  expect(Buffer.concat(chunks).toString("utf8")).toContain("data_mode\nCPI_TEST,DEMO");
});

test("global search keeps a deep ancestor path instead of flattening results", async ({ page }) => {
  await installApi(page, "demo");
  await page.goto("/data?view=v2");
  await page.getByLabel("搜索指标名称").fill("价格");
  await page.getByText("搜索全部", { exact: true }).click();

  const macro = page.getByRole("treeitem", { name: /宏观经济/ });
  await expect(macro).toHaveAttribute("aria-level", "1");
  await macro.click();
  const prices = page.getByRole("treeitem", { name: "价格 1", exact: true });
  await expect(prices).toHaveAttribute("aria-level", "2");
  await prices.click();
  const consumerPrices = page.getByRole("treeitem", { name: /居民价格/ });
  await expect(consumerPrices).toHaveAttribute("aria-level", "3");
  await consumerPrices.click();
  await expect(page.getByRole("treeitem", { name: "居民消费价格指数" })).toHaveAttribute("aria-level", "4");
  await expect(macro).toBeVisible();
  await expect(prices).toBeVisible();
  await expect(consumerPrices).toBeVisible();
});
