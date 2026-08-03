import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(resolve(process.cwd(), "app/globals.css"), "utf8");

function declarations(selector: string) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = stylesheet.match(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`));
  expect(match, `${selector} must have a CSS rule`).not.toBeNull();
  return match?.[1] ?? "";
}

describe("data browser responsive table containment", () => {
  it("contains the wide table inside its own horizontal scroller", () => {
    const card = declarations(".data-browser-table-card");
    const wrapper = declarations(".data-browser-table-wrap");

    expect(card).toMatch(/min-width:\s*0/);
    expect(card).toMatch(/max-width:\s*100%/);
    expect(card).toMatch(/overflow:\s*hidden/);
    expect(wrapper).toMatch(/min-width:\s*0/);
    expect(wrapper).toMatch(/max-width:\s*100%/);
    expect(wrapper).toMatch(/overflow:\s*auto/);
    expect(stylesheet).toMatch(/\.data-browser-table\s*\{[^}]*min-width:\s*690px/);
  });
});
