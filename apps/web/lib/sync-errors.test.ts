import { describe, expect, it } from "vitest";

import { formatTradingViewSyncError } from "./sync-errors";

describe("TradingView sync error messages", () => {
  it("turns a reset during the websocket handshake into an actionable message", () => {
    expect(formatTradingViewSyncError("ProviderDataError: TradingView WebSocket TLS connection failed: the remote server or outbound proxy reset the connection")).toBe(
      "同步失败：服务器到 TradingView 的连接在 TLS 握手阶段被重置，请检查服务器代理或出口防火墙。",
    );
    expect(formatTradingViewSyncError("ConnectionResetError: ")).toBe(
      "同步失败：服务器到 TradingView 的连接在 TLS 握手阶段被重置，请检查服务器代理或出口防火墙。",
    );
  });

  it("keeps unrelated worker errors visible", () => {
    expect(formatTradingViewSyncError("Provider returned no data")).toBe("Provider returned no data");
  });
});
