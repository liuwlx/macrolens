"use client";

import ReactECharts from "echarts-for-react";

import type { ObservationPoint } from "@/lib/types";

export function TimeSeriesChart({ series, height = 330 }: { series: Array<{ name: string; data: ObservationPoint[]; axis?: number }>; height?: number }) {
  const option = {
    animation: false,
    color: ["#1c4ed8", "#11a37f", "#e0a51b", "#d94c59", "#744ed8"],
    tooltip: { trigger: "axis", valueFormatter: (value: number) => value?.toLocaleString(undefined, { maximumFractionDigits: 3 }) },
    legend: { top: 0, left: 0, data: series.map((item) => item.name) },
    grid: { left: 45, right: series.some((item) => item.axis === 1) ? 50 : 20, top: 42, bottom: 38 },
    xAxis: { type: "category", boundaryGap: false, data: series[0]?.data.map((point) => point.period_start) ?? [], axisLabel: { color: "#8290a5", hideOverlap: true } },
    yAxis: [{ type: "value", scale: true, axisLabel: { color: "#8290a5" }, splitLine: { lineStyle: { color: "#edf0f5" } } }, ...(series.some((item) => item.axis === 1) ? [{ type: "value", scale: true, axisLabel: { color: "#8290a5" }, splitLine: { show: false } }] : [])],
    dataZoom: [{ type: "inside" }],
    series: series.map((item) => ({ name: item.name, type: "line", yAxisIndex: item.axis ?? 0, showSymbol: false, connectNulls: false, smooth: false, lineStyle: { width: 2 }, data: item.data.map((point) => point.value == null ? null : Number(point.value)) })),
  };
  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />;
}

export function BarChart({ labels, values, height = 260 }: { labels: string[]; values: number[]; height?: number }) {
  const option = { animation: false, tooltip: { trigger: "axis" }, grid: { left: 42, right: 15, top: 20, bottom: 42 }, xAxis: { type: "category", data: labels, axisLabel: { color: "#8290a5", hideOverlap: true } }, yAxis: { type: "value", axisLabel: { color: "#8290a5" }, splitLine: { lineStyle: { color: "#edf0f5" } } }, series: [{ type: "bar", data: values, itemStyle: { color: "#356be3", borderRadius: [5, 5, 0, 0] }, barMaxWidth: 38 }] };
  return <ReactECharts option={option} style={{ height }} notMerge lazyUpdate />;
}
