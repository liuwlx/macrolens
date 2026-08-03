import { expect, test } from "@playwright/test";

const widths = [390, 768, 1024, 1280];

for (const width of widths) {
  test(`data browser contains wide content at ${width}px`, async ({ browser }) => {
    const context = await browser.newContext({ viewport: { width, height: 844 } });
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
      return {
        innerWidth: window.innerWidth,
        documentWidth: document.documentElement.scrollWidth,
        wrapperClientWidth: wrapper?.clientWidth ?? 0,
        wrapperScrollWidth: wrapper?.scrollWidth ?? 0,
        wrapperOverflowX: wrapper ? getComputedStyle(wrapper).overflowX : "",
        tabsOverflowX: tabs ? getComputedStyle(tabs).overflowX : "",
      };
    });
    console.log(`${width}px layout: ${JSON.stringify(layout)}`);

    expect(layout.documentWidth).toBe(layout.innerWidth);
    expect(layout.wrapperOverflowX).toBe("auto");
    expect(layout.wrapperScrollWidth).toBeGreaterThan(layout.wrapperClientWidth);
    if (width === 390) expect(layout.tabsOverflowX).toBe("auto");

    await context.close();
  });
}
