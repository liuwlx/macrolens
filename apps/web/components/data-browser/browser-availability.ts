import type { BrowserSeriesAvailability } from "@/lib/types";

export type CatalogOnlyAvailability = Extract<
  BrowserSeriesAvailability,
  "pending_mapping" | "pending_credentials" | "pending_license"
>;

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
  return availability === "pending_mapping"
    || availability === "pending_credentials"
    || availability === "pending_license";
}

export function catalogOnlyReason(availability: CatalogOnlyAvailability): string {
  return `${browserAvailabilityLabels[availability]}：目录可见，但数据读取与发布保持关闭。`;
}
