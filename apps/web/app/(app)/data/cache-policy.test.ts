import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("data browser cache policy", () => {
  it("forces the authenticated data page to render dynamically", () => {
    const layout = readFileSync(resolve(process.cwd(), "app/(app)/data/layout.tsx"), "utf8");
    expect(layout).toContain('export const dynamic = "force-dynamic"');
    expect(layout).toContain("export const revalidate = 0");
  });
});
