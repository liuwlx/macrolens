import { expect, test } from "@playwright/test";

const viewports = [
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1280, height: 844 },
  { width: 1440, height: 900 },
  { width: 1920, height: 1080 },
  { width: 2560, height: 1280 },
];

for (const viewport of viewports) {
  test(`data browser contains wide content at ${viewport.width}px`, async ({ browser }) => {
    const context = await browser.newContext({ viewport });
    const page = await context.newPage();

    await page.route("**/api/v1/**", async (route) => {
      const path = new URL(route.request().url()).pathname;
      let body: unknown = {};
      if (path.endsWith("/auth/me")) {
        body = { id: "layout-user", email: "layout@example.test", display_name: "Layout", role: "admin" };
      } else if (path.endsWith("/series/browser")) {
        body = {
          items: [],
          facets: { provider: [], theme: [], frequency: [], unit: [], seasonal_adjustment: [] },
          pagination: { total: 0, limit: 20, offset: 0 },
          data_as_of: "2026-08-04T00:00:00Z",
        };
      } else if (path.endsWith("/taxonomies/macro-default/children")) {
        body = { tree_code: "macro-default", parent_id: null, nodes: [], series: [] };
      } else if (path.endsWith("/me/favorites")) {
        body = [];
      }
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
    });

    await page.goto("/data?view=v2");
    await expect(page.locator(".data-browser-table-wrap")).toBeVisible();

    const layout = await page.evaluate(() => {
      const wrapper = document.querySelector<HTMLElement>(".data-browser-table-wrap");
      const tabs = document.querySelector<HTMLElement>(".data-browser-tabs");
      const main = document.querySelector<HTMLElement>("main");
      const browserPage = document.querySelector<HTMLElement>(".data-browser-page");
      const workspace = document.querySelector<HTMLElement>(".data-browser-workspace");
      const sidebar = document.querySelector<HTMLElement>("aside.desktop-only");
      const workspaceRows = workspace
        ? getComputedStyle(workspace).gridTemplateRows.match(/[\d.]+px/g)?.map(Number.parseFloat) ?? []
        : [];
      const mainRect = main?.getBoundingClientRect();
      const pageRect = browserPage?.getBoundingClientRect();
      return {
        innerWidth: window.innerWidth,
        innerHeight: window.innerHeight,
        documentWidth: document.documentElement.scrollWidth,
        wrapperClientWidth: wrapper?.clientWidth ?? 0,
        wrapperScrollWidth: wrapper?.scrollWidth ?? 0,
        wrapperOverflowX: wrapper ? getComputedStyle(wrapper).overflowX : "",
        tabsOverflowX: tabs ? getComputedStyle(tabs).overflowX : "",
        mainPaddingLeft: main ? Number.parseFloat(getComputedStyle(main).paddingLeft) : 0,
        mainPaddingRight: main ? Number.parseFloat(getComputedStyle(main).paddingRight) : 0,
        sidebarWidth: sidebar?.getBoundingClientRect().width ?? 0,
        pageWidth: pageRect?.width ?? 0,
        leftContentGap: mainRect && pageRect ? pageRect.left - mainRect.left : 0,
        rightContentGap: mainRect && pageRect ? mainRect.right - pageRect.right : 0,
        bottomGap: pageRect ? Math.max(0, window.innerHeight - pageRect.bottom) : Number.POSITIVE_INFINITY,
        workspaceRows,
      };
    });
    console.log(`${viewport.width}px layout: ${JSON.stringify(layout)}`);

    expect(layout.documentWidth).toBe(layout.innerWidth);
    expect(layout.wrapperOverflowX).toBe("auto");
    expect(layout.wrapperScrollWidth).toBeGreaterThanOrEqual(layout.wrapperClientWidth);
    expect(layout.mainPaddingLeft).toBe(viewport.width < 768 ? 16 : 24);
    expect(layout.mainPaddingRight).toBe(viewport.width < 768 ? 16 : 24);
    if (viewport.width === 390) {
      expect(layout.wrapperScrollWidth).toBeGreaterThan(layout.wrapperClientWidth);
      expect(layout.tabsOverflowX).toBe("auto");
    }
    if (viewport.width >= 1280) {
      expect(layout.leftContentGap).toBeCloseTo(24, 0);
      expect(layout.rightContentGap).toBeCloseTo(24, 0);
      expect(layout.pageWidth).toBeGreaterThanOrEqual(
        layout.innerWidth - layout.sidebarWidth - 49,
      );
      expect(layout.workspaceRows[0]).toBeGreaterThanOrEqual(500);
      expect(layout.workspaceRows[1]).toBeGreaterThanOrEqual(300);
    }
    if (viewport.width === 2560) {
      expect(layout.workspaceRows[0] / layout.workspaceRows[1]).toBeGreaterThan(1.45);
      expect(layout.workspaceRows[0] / layout.workspaceRows[1]).toBeLessThan(1.55);
      expect(layout.bottomGap).toBeLessThanOrEqual(32);
    }

    await context.close();
  });
}
