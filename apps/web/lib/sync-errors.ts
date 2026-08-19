export function formatTradingViewSyncError(value: unknown): string {
  const message = value instanceof Error ? value.message : String(value ?? "");
  if (message.includes("ConnectionResetError") || message.includes("TradingView WebSocket connection failed")) {
    return "同步失败：服务器到 TradingView 的连接在 TLS 握手阶段被重置，请检查服务器代理或出口防火墙。";
  }
  return message || "TradingView同步失败";
}
