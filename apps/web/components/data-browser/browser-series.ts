import type { ObservationPoint } from "@/lib/types";

type Point = ObservationPoint & { numeric: number };

export function downsampleForDisplay(points: ObservationPoint[], threshold = 5000): ObservationPoint[] {
  if (points.length <= threshold || threshold < 3) return points;
  const usable = points.map((point) => ({ ...point, numeric: point.value == null ? Number.NaN : Number(point.value) }));
  const sampled: Point[] = [usable[0]];
  const bucketSize = (usable.length - 2) / (threshold - 2);
  let selectedIndex = 0;

  for (let bucket = 0; bucket < threshold - 2; bucket += 1) {
    const averageStart = Math.floor((bucket + 1) * bucketSize) + 1;
    const averageEnd = Math.min(Math.floor((bucket + 2) * bucketSize) + 1, usable.length);
    const averageSlice = usable.slice(averageStart, averageEnd).filter((point) => Number.isFinite(point.numeric));
    const averageX = averageSlice.length ? averageSlice.reduce((sum, _, index) => sum + averageStart + index, 0) / averageSlice.length : averageStart;
    const averageY = averageSlice.length ? averageSlice.reduce((sum, point) => sum + point.numeric, 0) / averageSlice.length : 0;
    const rangeStart = Math.floor(bucket * bucketSize) + 1;
    const rangeEnd = Math.min(Math.floor((bucket + 1) * bucketSize) + 1, usable.length - 1);
    const anchor = usable[selectedIndex];
    let largestArea = -1;
    let nextIndex = rangeStart;
    for (let index = rangeStart; index < rangeEnd; index += 1) {
      const candidate = usable[index];
      if (!Number.isFinite(candidate.numeric) || !Number.isFinite(anchor.numeric)) continue;
      const area = Math.abs((selectedIndex - averageX) * (candidate.numeric - anchor.numeric) - (selectedIndex - index) * (averageY - anchor.numeric));
      if (area > largestArea) { largestArea = area; nextIndex = index; }
    }
    selectedIndex = nextIndex;
    sampled.push(usable[selectedIndex]);
  }
  sampled.push(usable[usable.length - 1]);
  return sampled.map((point) => ({
    period_start: point.period_start,
    period_end: point.period_end,
    value: point.value,
    value_text: point.value_text,
    status: point.status,
    published_at: point.published_at,
    vintage_at: point.vintage_at,
  }));
}
