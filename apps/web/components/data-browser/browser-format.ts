import type { BrowserMetricValue } from "@/lib/types";

export function numericValue(value: number | string | null | undefined): number | null {
  if (value === null || value === undefined || value === "") return null;
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

export function formatNumber(value: number | string | null | undefined, decimalPlaces = 2): string {
  const parsed = numericValue(value);
  if (parsed === null) return "—";
  return parsed.toLocaleString("zh-CN", {
    minimumFractionDigits: Math.min(decimalPlaces, 2),
    maximumFractionDigits: Math.max(decimalPlaces, 0),
  });
}

export function formatMetric(metric: BrowserMetricValue | null | undefined, decimalPlaces = 2): string {
  const parsed = numericValue(metric?.value);
  if (!metric || metric.status !== "available" || parsed === null) return "—";
  const sign = parsed > 0 ? "+" : "";
  return `${sign}${formatNumber(parsed, Math.min(decimalPlaces + 1, 4))}${metric.unit ? ` ${metric.unit}` : ""}`;
}

export function metricTone(metric: BrowserMetricValue | null | undefined): "positive" | "negative" | "neutral" | "muted" {
  const parsed = numericValue(metric?.value);
  if (!metric || metric.status !== "available" || parsed === null) return "muted";
  if (parsed > 0) return "negative";
  if (parsed < 0) return "positive";
  return "neutral";
}

export function metricTitle(metric: BrowserMetricValue | null | undefined): string {
  if (!metric) return "没有可用数据";
  if (metric.status === "available") return metric.basis ? `口径：${metric.basis}` : "可用";
  return metric.reason ?? metric.reason_code ?? "历史不足或当前数据不可用";
}

export function formatLocalDate(value: string | null | undefined, withTime = false): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return withTime ? date.toLocaleString("zh-CN") : date.toLocaleDateString("zh-CN");
}

export function periodLabel(basis: string | null | undefined): string {
  return ({ mom: "环比", qoq: "季比", yoy: "同比", daily: "日变动", weekly: "周变动" } as Record<string, string>)[basis ?? ""] ?? "期间变化";
}
