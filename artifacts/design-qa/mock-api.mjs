import http from "node:http";

const port = 4010;
const snapshot = "2026-08-04T02:30:00Z";
const names = [
  ["CORE_PCE", "核心PCE价格指数", "通胀", "2.60", "2.80", "BEA"],
  ["CORE_SERVICES", "核心服务", "通胀", "3.88", "4.08", "BEA"],
  ["NONHOUSING_CORE", "非住房核心服务", "通胀", "4.40", "4.58", "BEA"],
  ["MEDICAL_SERVICES", "医疗服务", "通胀", "2.15", "2.38", "BEA"],
  ["HOSPITAL_SERVICES", "医院服务", "通胀", "2.37", "2.57", "BEA"],
  ["PHYSICIAN_SERVICES", "医生和诊疗服务", "通胀", "2.10", "2.27", "BEA"],
  ["OTHER_MEDICAL", "其他医疗专业服务", "通胀", "1.85", "2.02", "BEA"],
  ["DENTAL_SERVICES", "牙科服务", "通胀", "2.52", "2.84", "BEA"],
  ["MEDICAL_EQUIPMENT", "医疗设备及用品", "通胀", "1.28", "1.45", "BEA"],
  ["PRESCRIPTION_DRUGS", "处方药", "通胀", "0.78", "0.90", "BEA"],
  ["NONPRESCRIPTION", "非处方药", "通胀", "0.45", "0.49", "BEA"],
  ["HEALTH_INSURANCE", "健康保险", "通胀", "4.92", "5.14", "BEA"],
  ["LONG_TERM_CARE", "长期护理服务", "通胀", "3.65", "3.78", "BEA"],
  ["TRANSPORT_SERVICES", "交通服务", "通胀", "2.41", "2.69", "BEA"],
  ["RECREATION_SERVICES", "娱乐服务", "通胀", "1.98", "2.11", "BEA"],
  ["FOOD_SERVICES", "餐饮服务", "通胀", "3.11", "3.25", "BEA"],
  ["UNEMPLOYMENT", "失业率", "就业", "4.20", "4.10", "BLS"],
  ["NONFARM_PAYROLLS", "非农就业人数", "就业", "177000", "147000", "BLS"],
  ["REAL_GDP", "实际国内生产总值", "增长", "2.80", "1.40", "BEA"],
  ["RETAIL_SALES", "零售销售", "增长", "0.60", "0.30", "Census"],
  ["FED_FUNDS", "联邦基金目标利率", "利率与政策", "4.50", "4.50", "Federal Reserve"],
  ["US10Y", "美国10年期国债收益率", "金融市场", "4.11", "4.24", "Treasury"],
  ["DXY", "美元指数", "金融市场", "103.2", "104.1", "FRED"],
  ["CONSUMER_CREDIT", "消费者信贷", "信贷与银行", "5.70", "5.20", "Federal Reserve"],
];

const license = {
  display_allowed: true,
  download_allowed: true,
  api_redistribution_allowed: false,
  ai_context_allowed: true,
  attribution_required: true,
  attribution_text: "官方来源，仅用于本地验收",
};

const provider = (code) => ({ code, name: code === "BEA" ? "美国经济分析局" : code, attribution: code, license_class: "official" });
const metric = (value, basis = null) => ({ value, unit: "%", status: "available", reason_code: null, reason: null, basis });
const seriesItems = names.map(([code, name, theme, current, previous, source], index) => {
  const currentValue = Number(current);
  const previousValue = Number(previous);
  const change = currentValue - previousValue;
  return {
    series: {
      id: `series-${index + 1}`,
      canonical_code: code,
      name_zh: name,
      name_en: name,
      theme,
      frequency: "monthly",
      unit_code: code === "NONFARM_PAYROLLS" ? "persons" : "percent",
      unit_label_zh: code === "NONFARM_PAYROLLS" ? "人" : "%",
      default_transform: "yoy",
      latest_period: "2026-06-30",
      latest_value: currentValue,
      latest_vintage_at: snapshot,
      provider: provider(source),
      decimal_places: code === "NONFARM_PAYROLLS" ? 0 : 2,
      seasonal_adjustment: "seasonally_adjusted",
      description: `${name}用于衡量相关宏观经济活动的变化，当前页面使用固定验收快照。`,
    },
    current: { period_start: "2026-06-01", period_end: "2026-06-30", value: currentValue, published_at: "2026-07-31T12:30:00Z", vintage_at: snapshot },
    previous: { period_start: "2026-05-01", period_end: "2026-05-31", value: previousValue, published_at: "2026-06-28T12:30:00Z", vintage_at: "2026-07-01T12:30:00Z" },
    change: metric(Number(change.toFixed(2)), "monthly"),
    period_change: metric(Number((change * 0.62).toFixed(2)), "mom"),
    yoy: metric(Number((change * 3.1).toFixed(2)), "yoy"),
    license,
    display_denied: false,
    source_status: "verified",
    unavailable_reason_code: null,
    taxonomy_order: index,
  };
});

const facets = {
  provider: ["BEA", "BLS", "Federal Reserve", "Treasury"].map((value, index) => ({ value, label: value, count: 18 - index * 3 })),
  theme: ["通胀", "就业", "增长", "利率与政策", "金融市场", "信贷与银行"].map((value, index) => ({ value, label: value, count: 16 - index * 2 })),
  frequency: [{ value: "monthly", label: "月度", count: 24 }],
  unit: [{ value: "percent", label: "%", count: 22 }, { value: "persons", label: "人", count: 2 }],
  seasonal_adjustment: [{ value: "seasonally_adjusted", label: "季调", count: 24 }],
};

const tree = {
  root: {
    nodes: [
      ["inflation", "通胀（Prices / Inflation）", 16],
      ["labor", "就业（Labor Market）", 2],
      ["growth", "增长（Growth）", 2],
      ["rates", "利率与政策（Rates & Policy）", 1],
      ["financial", "金融市场（Financial Markets）", 2],
      ["credit", "信贷与银行（Credit & Banking）", 1],
    ].map(([id, name_zh, count]) => ({ id, code: id, name_zh, name_en: name_zh, node_type: "theme", icon_key: "folder", has_children: true, direct_series_count: 0, descendant_series_count: count })),
    series: [],
  },
  inflation: {
    nodes: [["pce", "PCE（个人消费支出价格指数）", 16]].map(([id, name_zh, count]) => ({ id, code: id, name_zh, name_en: name_zh, node_type: "category", icon_key: "folder", has_children: true, direct_series_count: 0, descendant_series_count: count })),
    series: [],
  },
  pce: {
    nodes: [["core", "核心PCE价格指数（剔除食品和能源）", 15]].map(([id, name_zh, count]) => ({ id, code: id, name_zh, name_en: name_zh, node_type: "category", icon_key: "folder", has_children: true, direct_series_count: 1, descendant_series_count: count })),
    series: seriesItems.slice(0, 1).map((item) => item.series),
  },
  core: { nodes: [], series: seriesItems.slice(1, 16).map((item) => item.series) },
  labor: { nodes: [], series: seriesItems.slice(16, 18).map((item) => item.series) },
  growth: { nodes: [], series: seriesItems.slice(18, 20).map((item) => item.series) },
  rates: { nodes: [], series: seriesItems.slice(20, 21).map((item) => item.series) },
  financial: { nodes: [], series: seriesItems.slice(21, 23).map((item) => item.series) },
  credit: { nodes: [], series: seriesItems.slice(23).map((item) => item.series) },
};

function points(index = 0) {
  const result = [];
  for (let month = 0; month < 84; month += 1) {
    const date = new Date(Date.UTC(2019 + Math.floor(month / 12), month % 12, 1));
    const baseline = index === 3 ? 1.6 + Math.sin(month / 8) * 0.5 + Math.max(0, 5 - Math.abs(month - 48) / 8) : 2.2 + Math.sin(month / 7) * 0.35 + index * 0.07;
    result.push({
      period_start: date.toISOString().slice(0, 10),
      period_end: new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 0)).toISOString().slice(0, 10),
      value: Number(baseline.toFixed(2)),
      status: month === 82 ? "revised" : "normal",
      published_at: new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 28, 12, 30)).toISOString(),
      vintage_at: new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth() + 1, 28, 12, 30)).toISOString(),
    });
  }
  return result;
}

function json(res, body, status = 200) {
  res.writeHead(status, { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true", "Cache-Control": "no-store" });
  res.end(JSON.stringify(body));
}

function csv(res, filename) {
  res.writeHead(200, { "Content-Type": "text/csv; charset=utf-8", "Content-Disposition": `attachment; filename="${filename}"`, "Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true", "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" });
  res.end("series_code,period,value\nMEDICAL_SERVICES,2026-06,2.15\n");
}

function browserPayload(url) {
  const q = (url.searchParams.get("q") ?? "").toLowerCase();
  const theme = url.searchParams.get("theme") ?? "";
  const offset = Number(url.searchParams.get("offset") ?? 0);
  const limit = Number(url.searchParams.get("limit") ?? 20);
  const filtered = seriesItems.filter((item) => (!q || `${item.series.canonical_code} ${item.series.name_zh}`.toLowerCase().includes(q)) && (!theme || item.series.theme === theme));
  return { items: filtered.slice(offset, offset + limit), facets, pagination: { total: filtered.length, limit, offset }, data_as_of: snapshot };
}

const server = http.createServer((req, res) => {
  if (!req.url) return json(res, { detail: "missing url" }, 400);
  if (req.method === "OPTIONS") {
    res.writeHead(204, { "Access-Control-Allow-Origin": "http://localhost:3000", "Access-Control-Allow-Credentials": "true", "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Allow-Methods": "GET,POST,DELETE,PATCH,OPTIONS" });
    return res.end();
  }
  const url = new URL(req.url, `http://localhost:${port}`);
  const path = url.pathname.replace(/^\/api\/v1/, "");
  if (path === "/health") return json(res, { ok: true });
  if (path === "/auth/me") return json(res, { id: "admin-1", email: "admin@example.com", display_name: "研究员小陈", role: "admin" });
  if (path === "/auth/refresh") return json(res, { ok: true });
  if (path === "/me/notifications") return json(res, [{ id: "n-1", notification_type: "release", title: "核心PCE已更新", body: "固定验收快照", action_url: "/data", payload: {}, created_at: snapshot, read_at: null }]);
  if (path === "/me/favorites" && req.method === "GET") return json(res, []);
  if (path === "/me/favorites" && req.method === "POST") return json(res, { id: "fav-1", object_type: "series", object_id: "series-1", group_name: "重点指标", note: null, sort_order: 0, created_at: snapshot });
  if (path.startsWith("/me/favorites/") && req.method === "DELETE") return json(res, null, 204);
  if (path === "/series/browser") return json(res, browserPayload(url));
  if (path === "/series/browser/export") return csv(res, "macrolens-data-browser.csv");
  if (path === "/taxonomies/macro-default/children") {
    const key = url.searchParams.get("parent_id") ?? "root";
    return json(res, { tree_code: "macro-default", parent_id: key === "root" ? null : key, ...(tree[key] ?? { nodes: [], series: [] }) });
  }
  if (path === "/ai/capabilities") return json(res, { configured: true, allowed: true, reason_code: null, reason: null });
  const match = path.match(/^\/series\/(series-(\d+))(\/.*)?$/);
  if (match) {
    const index = Math.max(0, Number(match[2]) - 1);
    const item = seriesItems[index] ?? seriesItems[0];
    const suffix = match[3] ?? "";
    if (suffix === "") return json(res, { ...item.series, description: item.series.description, seasonal_adjustment: "seasonally_adjusted", geography_code: "US", decimal_places: item.series.decimal_places, status: "active", first_period: "2019-01-01", aliases: [] });
    if (suffix === "/observations") return json(res, { series: item.series, data: points(index), meta: { data_as_of: snapshot, vintage: "latest", transform: url.searchParams.get("transform") ?? "yoy", frequency: "monthly", unit: "%", lineage: { provider: item.series.provider.code, dataset: "Local acceptance fixture", provider_series_id: item.series.canonical_code, source_series_id: index + 1, source_locator: {} }, license } });
    if (suffix === "/analytics") return json(res, { statistics: { count: 84, mean: 2.36, median: 2.18, min: 0.28, max: 5.62, stddev: 1.32, current_percentile: 58 }, next_release: { id: "release-1", title_zh: "个人收入和支出", scheduled_at: "2026-08-28T12:30:00Z", source_timezone: "America/New_York", status: "scheduled", role: "headline" }, contributions: { available: true, reason_code: null, reason: null, target_unit: "百分点", periods: points(index).slice(-24).map((point) => ({ period_start: point.period_start, target_value: Number(point.value) })), components: ["核心商品", "住房服务", "非住房核心服务", "医疗服务"].map((name, component) => ({ series_id: `component-${component}`, name_zh: name, values: points(index).slice(-24).map((_, i) => Number((0.25 + component * 0.13 + Math.sin(i / 4) * 0.08).toFixed(2))) })), reconciliation: { passed: true, tolerance: 0.01, difference: 0 } }, capabilities: Object.fromEntries(["display", "download", "ai", "trend", "history", "revisions", "documents", "contributions"].map((key) => [key, { allowed: true, reason_code: null, reason: null }])), data_as_of: snapshot });
    if (suffix === "/revisions") return json(res, { items: [{ period_start: "2026-05-01", versions: 2, latest_value: 2.38, previous_value: 2.31, absolute_revision: 0.07 }] });
    if (suffix === "/export") return csv(res, `${item.series.canonical_code}.csv`);
  }
  if (path === "/documents") return json(res, { items: [], total: 0 });
  return json(res, { type: "about:blank", title: "Not Found", status: 404, detail: `No fixture for ${path}` }, 404);
});

server.listen(port, "127.0.0.1", () => console.log(`MacroLens design QA fixture API: http://localhost:${port}/api/v1`));
