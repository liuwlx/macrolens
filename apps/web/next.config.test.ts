import { afterEach, describe, expect, it } from "vitest";

import nextConfig from "./next.config";

const originalNextPublicApiUrl = process.env.NEXT_PUBLIC_API_URL;
const originalApiInternalUrl = process.env.API_INTERNAL_URL;

afterEach(() => {
  if (originalNextPublicApiUrl === undefined) {
    delete process.env.NEXT_PUBLIC_API_URL;
  } else {
    process.env.NEXT_PUBLIC_API_URL = originalNextPublicApiUrl;
  }
  if (originalApiInternalUrl === undefined) {
    delete process.env.API_INTERNAL_URL;
  } else {
    process.env.API_INTERNAL_URL = originalApiInternalUrl;
  }
});

describe("Next.js API proxy", () => {
  it("forwards the same-origin public API path to the internal API", async () => {
    process.env.NEXT_PUBLIC_API_URL = "/api/v1";

    const rewrites = await nextConfig.rewrites?.();

    expect(rewrites).toEqual([
      {
        source: "/api/v1/:path*",
        destination: "http://api:8000/api/v1/:path*",
      },
    ]);
  });

  it("uses the configured internal API URL", async () => {
    process.env.NEXT_PUBLIC_API_URL = "/api/v1";
    process.env.API_INTERNAL_URL = "http://acceptance-api:9000/internal/v1";

    const rewrites = await nextConfig.rewrites?.();

    expect(rewrites).toEqual([
      {
        source: "/api/v1/:path*",
        destination: "http://acceptance-api:9000/internal/v1/:path*",
      },
    ]);
  });

  it("preserves the existing security headers", async () => {
    await expect(nextConfig.headers?.()).resolves.toEqual([
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ]);
  });
});
