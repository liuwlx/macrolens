import { expect, type Page, test } from "@playwright/test";

/* eslint-disable @typescript-eslint/no-explicit-any --
 * This runtime acceptance test intentionally traverses heterogeneous API payloads. The assertions
 * validate their observable contract; duplicating every production response schema here would
 * couple the E2E boundary to implementation-owned TypeScript types.
 */

const adminEmail = process.env.E2E_ADMIN_EMAIL ?? "admin@example.com";
const adminPassword = process.env.E2E_ADMIN_PASSWORD ?? "change-me-now";
const apiUrl = process.env.E2E_API_URL ?? "http://localhost:8000/api/v1";

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function runtimeReleaseWindow(): { start: string; end: string } {
  const now = new Date();
  const start = new Date(now);
  const end = new Date(now);
  start.setUTCFullYear(start.getUTCFullYear() - 1);
  end.setUTCFullYear(end.getUTCFullYear() + 1);
  return { start: isoDate(start), end: isoDate(end) };
}

type Json = Record<string, any> | any[] | string | number | boolean | null;

async function login(page: Page) {
  await page.goto("/login");
  await page.getByLabel("邮箱").fill(adminEmail);
  await page.getByLabel("密码").fill(adminPassword);
  await page.getByRole("button", { name: /^登录$/ }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /宏观总览/ })).toBeVisible();
}

async function api<T extends Json>(
  page: Page,
  path: string,
  init: { method?: string; body?: unknown; headers?: Record<string, string> } = {},
): Promise<T> {
  return page.evaluate(
    async ({ base, path, init }) => {
      const response = await fetch(`${base}${path}`, {
        method: init.method ?? "GET",
        credentials: "include",
        headers: init.body === undefined ? { Accept: "application/json", ...init.headers } : {
          Accept: "application/json",
          "Content-Type": "application/json",
          ...init.headers,
        },
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
      });
      const text = await response.text();
      const payload = text ? JSON.parse(text) : null;
      if (!response.ok) {
        throw new Error(`${response.status} ${path}: ${payload?.detail ?? payload?.message ?? text}`);
      }
      return payload;
    },
    { base: apiUrl, path, init },
  ) as Promise<T>;
}

test.beforeEach(async ({ page }) => {
  await login(page);
});

test("all researcher pages render their production data states", async ({ page }) => {
  const routes: Array<[string, RegExp]> = [
    ["/", /宏观总览/],
    ["/data", /指标与时间序列/],
    ["/calendar", /宏观事件与数据发布/],
    ["/fomc", /会议追踪与政策观察/],
    ["/documents", /宏观文档与研究资料/],
    ["/ai", /宏观研究助理/],
    ["/compare", /对比分析/],
    ["/workspace", /研究工作台/],
    ["/favorites", /收藏/],
    ["/alerts", /提醒中心/],
    ["/reports", /报告中心/],
    ["/admin", /数据运营控制台/],
  ];
  for (const [route, heading] of routes) {
    await page.goto(route);
    await expect(page.getByRole("heading", { name: heading }).first()).toBeVisible();
    await expect(page.getByText("加载失败")).toHaveCount(0);
    await expect(page.getByText(/Internal Server Error/i)).toHaveCount(0);
  }
});

test("data, release, FOMC and document read paths return linked runtime fixtures", async ({ page }) => {
  const series = await api<{ items: any[]; total: number }>(page, "/series?limit=20");
  expect(series.total).toBeGreaterThanOrEqual(3);
  expect(series.items.length).toBeGreaterThanOrEqual(3);

  const first = series.items[0];
  const second = series.items[1];
  const detail = await api<any>(page, `/series/${first.id}`);
  expect(detail.canonical_code).toBe(first.canonical_code);
  const observations = await api<any>(page, `/series/${first.id}/observations?transform=level`);
  expect(observations.data.length).toBeGreaterThanOrEqual(60);
  expect(observations.meta.lineage).toBeTruthy();
  expect(observations.meta.license).toBeTruthy();
  const revisions = await api<any>(page, `/series/${first.id}/revisions`);
  expect(revisions.items.some((item: any) => item.versions >= 2)).toBeTruthy();

  const compared = await api<any>(page, "/compare/query", {
    method: "POST",
    body: {
      series: [
        { series_id: first.id, transform: "level", lag_periods: 0, axis: "left" },
        { series_id: second.id, transform: "zscore", lag_periods: 0, axis: "right" },
      ],
      include_correlation: true,
    },
  });
  expect(compared.items).toHaveLength(2);
  expect(compared.correlations.length).toBeGreaterThan(0);

  const releaseWindow = runtimeReleaseWindow();
  const releases = await api<{ items: any[] }>(
    page,
    `/release-events?start=${releaseWindow.start}&end=${releaseWindow.end}&limit=100`,
  );
  expect(releases.items.length).toBeGreaterThan(0);
  const release = await api<any>(page, `/release-events/${releases.items[0].id}`);
  expect(release.metrics.length).toBeGreaterThan(0);
  expect(release.forecasts.length).toBeGreaterThan(0);
  expect(release.market_reactions.length).toBeGreaterThan(0);

  const meetings = await api<{ items: any[] }>(page, "/fomc/meetings?limit=100");
  expect(meetings.items.length).toBeGreaterThan(0);
  const fixtureMeeting = meetings.items.find((item: any) => item.meeting_start === "2026-07-28");
  expect(fixtureMeeting).toBeTruthy();
  const meeting = await api<any>(page, `/fomc/meetings/${fixtureMeeting.id}`);
  expect(meeting.projections.length).toBeGreaterThan(0);
  expect(meeting.dots.length).toBeGreaterThan(0);
  const probabilities = await api<any[]>(page, `/fomc/meetings/${fixtureMeeting.id}/probabilities`);
  expect(probabilities.length).toBeGreaterThan(0);

  const documents = await api<{ items: any[] }>(page, "/documents?limit=100");
  expect(documents.items.length).toBeGreaterThan(0);
  const document = await api<any>(page, `/documents/${documents.items[0].id}/content`);
  expect(document.chunks.length).toBeGreaterThan(0);
  expect(document.summary_zh).toBeTruthy();
});

test("workspace mutations, alerts, favorites and sharing form a complete research workflow", async ({ page }) => {
  const suffix = Date.now().toString();
  const series = await api<{ items: any[] }>(page, "/series?limit=20");
  const targetSeries = series.items[2];

  const favorite = await api<any>(page, "/me/favorites", {
    method: "POST",
    body: { object_type: "series", object_id: targetSeries.id, group_name: "E2E", note: suffix },
  });
  expect(favorite.object_id).toBe(targetSeries.id);

  const view = await api<any>(page, "/me/saved-views", {
    method: "POST",
    body: {
      name: `E2E对比视图-${suffix}`,
      view_type: "compare",
      definition: { series: [{ series_id: targetSeries.id, transform: "level", axis: "left", lag_periods: 0 }] },
      description: "runtime acceptance",
    },
  });
  const updatedView = await api<any>(page, `/me/saved-views/${view.id}`, {
    method: "PATCH",
    body: { is_shared: true, description: "updated by E2E" },
  });
  expect(updatedView.is_shared).toBeTruthy();

  const project = await api<any>(page, "/me/projects", {
    method: "POST",
    body: { name: `E2E研究项目-${suffix}`, description: "full workflow" },
  });
  const projectItem = await api<any>(page, `/me/projects/${project.id}/items`, {
    method: "POST",
    body: { object_type: "series", object_id: targetSeries.id, title_override: "E2E指标", metadata: {} },
  });
  expect(projectItem.created).toBeTruthy();
  const note = await api<any>(page, `/me/projects/${project.id}/notes`, {
    method: "POST",
    body: { title: "E2E笔记", body_markdown: "事实、推断、风险分开记录。" },
  });
  const changedNote = await api<any>(page, `/me/projects/${project.id}/notes/${note.id}`, {
    method: "PATCH",
    body: { title: "E2E笔记已更新", body_markdown: "更新后的可审计研究笔记。" },
  });
  expect(changedNote.version_no).toBe(2);
  const share = await api<any>(page, `/me/projects/${project.id}/shares`, {
    method: "POST",
    body: { expires_in_days: 7 },
  });
  expect(share.share_url).toContain("/shared/project/");
  const token = share.share_url.split("/").pop();
  const publicProject = await api<any>(page, `/shared/projects/${token}`);
  expect(publicProject.name).toBe(project.name);

  const alert = await api<any>(page, "/me/alerts", {
    method: "POST",
    body: {
      name: `E2E阈值提醒-${suffix}`,
      alert_type: "threshold",
      target_type: "series",
      target_id: targetSeries.id,
      rule: { operator: ">=", value: 1, cooldown_hours: 24 },
      channels: ["in_app"],
    },
  });
  const paused = await api<any>(page, `/me/alerts/${alert.id}?active=false`, { method: "PATCH" });
  expect(paused.active).toBeFalsy();

  const notifications = await api<any[]>(page, "/me/notifications");
  expect(notifications.length).toBeGreaterThan(0);
  const marked = await api<any>(page, `/me/notifications/${notifications[0].id}/read`, { method: "POST" });
  expect(marked.read_at).toBeTruthy();

  const projectDetail = await api<any>(page, `/me/projects/${project.id}`);
  expect(projectDetail.items.length).toBe(1);
  expect(projectDetail.notes.length).toBe(1);

  await api(page, `/me/projects/${project.id}/shares/${share.id}`, { method: "DELETE" });
  await api(page, `/me/alerts/${alert.id}`, { method: "DELETE" });
  await api(page, `/me/saved-views/${view.id}`, { method: "DELETE" });
  await api(page, `/me/favorites/${favorite.id}`, { method: "DELETE" });
  await api(page, `/me/projects/${project.id}`, { method: "DELETE" });
});

test("AI worker produces citations and report lifecycle completes", async ({ page }) => {
  const documents = await api<{ items: any[] }>(page, "/documents?limit=20");
  const document = documents.items[0];
  const run = await api<any>(page, "/ai/runs", {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
    body: {
      prompt: "请基于官方文档分析核心PCE变化及政策风险，并给出可核验引用。",
      mode: "quick",
      contexts: [{ context_type: "document", context_id: document.id }],
    },
  });
  expect(run.status).toBe("queued");

  await expect.poll(
    async () => (await api<any>(page, `/ai/runs/${run.id}`)).status,
    { timeout: 90_000, intervals: [500, 1000, 2000, 3000] },
  ).toBe("completed");
  const completed = await api<any>(page, `/ai/runs/${run.id}`);
  expect(completed.result_markdown).toContain("[1]");
  const citations = await api<any[]>(page, `/ai/runs/${run.id}/citations`);
  expect(citations.length).toBeGreaterThan(0);
  expect(citations[0].document_chunk_id).toBeTruthy();

  const report = await api<any>(page, "/me/reports", {
    method: "POST",
    body: { title: `E2E AI报告-${Date.now()}`, ai_run_id: run.id, status: "draft" },
  });
  expect(report.content_markdown).toContain("[1]");
  const published = await api<any>(page, `/me/reports/${report.id}`, {
    method: "PATCH",
    body: { status: "published", title: `${report.title}-已发布` },
  });
  expect(published.status).toBe("published");
  await api(page, `/me/reports/${report.id}`, { method: "DELETE" });
});

test("admin operational endpoints expose providers, jobs, mappings and quality state", async ({ page }) => {
  const [providers, jobs, mappings, users, batches, quality] = await Promise.all([
    api<any[]>(page, "/admin/providers"),
    api<any[]>(page, "/admin/jobs?limit=100"),
    api<any[]>(page, "/admin/source-mappings?limit=500"),
    api<any[]>(page, "/admin/users"),
    api<any[]>(page, "/admin/publication-batches?limit=100"),
    api<any[]>(page, "/admin/quality-results?limit=100"),
  ]);
  expect(providers.length).toBeGreaterThan(0);
  expect(Array.isArray(jobs)).toBeTruthy();
  expect(mappings.length).toBeGreaterThanOrEqual(50);
  expect(users.some((user) => user.email === adminEmail)).toBeTruthy();
  expect(batches.length).toBeGreaterThan(0);
  expect(Array.isArray(quality)).toBeTruthy();
});

test("login page is responsive and safe redirect validation remains local", async ({ browser }) => {
  const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  await page.goto("/login?next=https://attacker.example/path");
  await expect(page.getByLabel("邮箱")).toBeVisible();
  await expect(page.getByLabel("密码")).toBeVisible();
  await page.getByLabel("邮箱").fill(adminEmail);
  await page.getByLabel("密码").fill(adminPassword);
  await page.getByRole("button", { name: /^登录$/ }).click();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole("heading", { name: /宏观总览/ })).toBeVisible();
  await context.close();
});
