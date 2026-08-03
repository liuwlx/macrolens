import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiFetch, queryString } from "./api";

describe("queryString", () => {
  it("encodes supported values and drops empty values", () => {
    expect(queryString({ q: "核心 PCE", limit: 20, active: false, empty: "", nil: null })).toBe(
      "?q=%E6%A0%B8%E5%BF%83+PCE&limit=20&active=false",
    );
  });

  it("returns an empty suffix for empty input", () => {
    expect(queryString({})).toBe("");
  });
});

describe("apiFetch", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns a parsed JSON response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 })));
    await expect(apiFetch<{ ok: boolean }>("/health")).resolves.toEqual({ ok: true });
  });

  it("throws a typed API error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "not found", code: "missing" }), {
          status: 404,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    await expect(apiFetch("/missing")).rejects.toMatchObject({ status: 404, code: "missing" } satisfies Partial<ApiError>);
  });
});
