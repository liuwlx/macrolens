import { describe, expect, it } from "vitest";

import type { BrowserSeriesAvailability, SeriesBrowserItem } from "@/lib/types";

import { browserDataCapabilityState } from "./browser-availability";

function item(availability: BrowserSeriesAvailability): SeriesBrowserItem {
  return {
    availability,
    series: {
      id: "series-1",
      canonical_code: "US.TEST",
      name_zh: "测试指标",
      theme: "activity",
      frequency: "monthly",
      unit_code: "index",
      unit_label_zh: "指数",
      default_transform: "level",
    },
    current: null,
    previous: null,
    change: { value: null, status: "unavailable" },
    period_change: { value: null, status: "unavailable" },
    yoy: { value: null, status: "unavailable" },
    display_denied: false,
  };
}

describe("browserDataCapabilityState", () => {
  it("fails closed while the deep-linked browser item is unresolved", () => {
    expect(browserDataCapabilityState(undefined, false)).toBe("unknown");
    expect(browserDataCapabilityState(undefined, true)).toBe("unknown");
  });

  it.each([
    "pending_mapping",
    "pending_credentials",
    "pending_license",
    "not_ingested",
    "not_available_as_of",
    "not_available_for_geography",
  ] as const)("treats %s as catalog-only", (availability) => {
    expect(browserDataCapabilityState(item(availability), true)).toBe("catalog_only");
  });

  it("opens data capabilities only for a resolved available item", () => {
    expect(browserDataCapabilityState(item("available"), true)).toBe("data_ready");
    expect(browserDataCapabilityState(item("available"), false)).toBe("unknown");
  });
});
