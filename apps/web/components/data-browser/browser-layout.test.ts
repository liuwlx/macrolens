import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const stylesheet = readFileSync(resolve(process.cwd(), "app/globals.css"), "utf8");
const appShell = readFileSync(resolve(process.cwd(), "components/app-shell.tsx"), "utf8");

function declarations(selector: string) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = stylesheet.match(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`));
  expect(match, `${selector} must have a CSS rule`).not.toBeNull();
  return match?.[1] ?? "";
}

function allDeclarations(selector: string) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return Array.from(stylesheet.matchAll(new RegExp(`${escaped}\\s*\\{([^}]+)\\}`, "g")), (match) => match[1]);
}

describe("data browser responsive table containment", () => {
  it("keeps authenticated content fluid with the established responsive padding", () => {
    expect(appShell).not.toContain("max-w-[1720px]");
    expect(appShell).not.toMatch(/<main[^>]*\bmx-auto\b/);
    expect(appShell).toMatch(/<main[^>]*\bmin-w-0\b[^>]*\bw-full\b/);
    expect(appShell).toMatch(/<main[^>]*\bp-4\b[^>]*\bmd:p-6\b/);
  });

  it("fills the desktop viewport with a bounded three-to-two workspace", () => {
    const desktopStart = stylesheet.indexOf("@media (min-width: 1280px)");
    const desktopEnd = stylesheet.indexOf("@media", desktopStart + 1);
    const desktopRules = stylesheet.slice(desktopStart, desktopEnd);

    expect(desktopStart).toBeGreaterThanOrEqual(0);
    expect(desktopRules).toMatch(/\.data-browser-page\s*\{[^}]*min-height:\s*calc\(100dvh - 124px\)/);
    expect(desktopRules).toMatch(/\.data-browser-page\s*\{[^}]*display:\s*flex/);
    expect(desktopRules).toMatch(/\.data-browser-workspace\s*\{[^}]*min-height:\s*812px/);
    expect(desktopRules).toMatch(/grid-template-rows:\s*minmax\(500px, 3fr\) minmax\(300px, 2fr\)/);
  });

  it("contains the wide table inside its own horizontal scroller", () => {
    const page = declarations(".data-browser-page");
    const card = declarations(".data-browser-table-card");
    const wrapper = declarations(".data-browser-table-wrap");

    expect(page).toMatch(/min-width:\s*0/);
    expect(page).toMatch(/max-width:\s*100%/);
    expect(page).toMatch(/overflow-x:\s*clip/);
    expect(card).toMatch(/min-width:\s*0/);
    expect(card).toMatch(/max-width:\s*100%/);
    expect(card).toMatch(/overflow:\s*hidden/);
    expect(wrapper).toMatch(/min-width:\s*0/);
    expect(wrapper).toMatch(/max-width:\s*100%/);
    expect(wrapper).toMatch(/overflow:\s*auto/);
    expect(allDeclarations(".data-browser-tabs").some((rule) => /overflow-x:\s*auto/.test(rule))).toBe(true);
    expect(stylesheet).toMatch(/\.data-browser-table\s*\{[^}]*min-width:\s*690px/);
  });
});
