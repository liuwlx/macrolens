import { describe, expect, it } from "vitest";

import { defaultBrowserState, parseBrowserState, patchBrowserState, serializeBrowserState } from "./browser-query";

describe("data browser URL state", () => {
  it("round-trips shareable filters and analysis state", () => {
    const source = new URLSearchParams("q=PCE&series=s1&node=n1&page=3&sort=yoy&order=desc&tab=history&transform=yoy&view=v2");
    const parsed = parseBrowserState(source);
    expect(parsed).toMatchObject({ q: "PCE", series: "s1", node: "n1", page: 3, sort: "yoy", order: "desc", tab: "history", transform: "yoy" });
    expect(serializeBrowserState(parsed, source).toString()).toContain("view=v2");
    expect(parseBrowserState(serializeBrowserState(parsed))).toEqual(parsed);
  });

  it("resets pagination when a filter changes", () => {
    expect(patchBrowserState({ ...defaultBrowserState, page: 4 }, { provider: "BEA" }).page).toBe(1);
  });

  it("sanitizes unsupported values", () => {
    const state = parseBrowserState(new URLSearchParams("page=-2&sort=invalid&order=sideways&tab=unknown"));
    expect(state).toMatchObject({ page: 1, sort: "taxonomy", order: "asc", tab: "trend" });
  });
});
