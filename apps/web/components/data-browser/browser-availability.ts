import type { BrowserSeriesAvailability, SeriesBrowserItem } from "@/lib/types";

export type CatalogOnlyAvailability = Extract<
  BrowserSeriesAvailability,
  | "pending_mapping"
  | "pending_credentials"
  | "pending_license"
  | "not_ingested"
  | "not_available_as_of"
>;

export type BrowserDataCapabilityState = "unknown" | "catalog_only" | "data_ready";

export const browserAvailabilityLabels: Record<
  Exclude<BrowserSeriesAvailability, "available">,
  string
> = {
  pending_mapping: "待映射",
  pending_credentials: "待凭据",
  pending_license: "待许可",
  not_ingested: "尚未采集",
  not_available_as_of: "该快照不可用",
};

export function isCatalogOnlyAvailability(
  availability?: BrowserSeriesAvailability,
): availability is CatalogOnlyAvailability {
  return availability !== undefined && availability !== "available";
}

export function browserDataCapabilityState(
  item: SeriesBrowserItem | undefined,
  browserResolved: boolean,
): BrowserDataCapabilityState {
  if (!browserResolved || item === undefined) return "unknown";
  return isCatalogOnlyAvailability(item.availability) ? "catalog_only" : "data_ready";
}

export function catalogOnlyReason(availability: CatalogOnlyAvailability): string {
  return `${browserAvailabilityLabels[availability]}：目录可见，但数据读取与发布保持关闭。`;
}
