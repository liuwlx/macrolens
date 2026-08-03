import { describe, expect, it } from "vitest";

import { formatMetric, metricTitle, metricTone } from "./browser-format";

describe("data browser metric formatting", () => {
  it("adds signs and follows the confirmed positive-red negative-green convention", () => {
    expect(formatMetric({ value: 0.24, unit: "pp", status: "available" }, 2)).toBe("+0.24 pp");
    expect(metricTone({ value: 0.24, status: "available" })).toBe("negative");
    expect(metricTone({ value: -0.24, status: "available" })).toBe("positive");
  });

  it("does not turn missing data into zero", () => {
    const metric = { value: null, status: "unavailable" as const, reason: "历史不足" };
    expect(formatMetric(metric)).toBe("—");
    expect(metricTitle(metric)).toBe("历史不足");
  });
});
