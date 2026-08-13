"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BookOpenText, CalendarRange, FileClock, Info, LineChart, RefreshCw } from "lucide-react";
import { useMemo, useRef } from "react";

import { ContributionChart, TimeSeriesChart } from "@/components/chart";
import { apiFetch, queryString } from "@/lib/api";
import type { DocumentSummary, ObservationResponse, RevisionResponse, SeriesAnalyticsResponse, SeriesBrowserItem } from "@/lib/types";

import { catalogOnlyReason, type BrowserDataCapabilityState } from "./browser-availability";
import { downsampleForDisplay } from "./browser-series";
import { formatLocalDate, formatNumber } from "./browser-format";
import type { BrowserState, BrowserTab } from "./browser-query";

type Props = {
  state: BrowserState;
  item?: SeriesBrowserItem;
  capabilityState: BrowserDataCapabilityState;
  analytics?: SeriesAnalyticsResponse;
  analyticsLoading: boolean;
  analyticsError?: Error | null;
  onChange(patch: Partial<BrowserState>): void;
  onRetryAnalytics(): void;
};

const tabs: Array<{ id: BrowserTab; label: string; icon: typeof LineChart }> = [
  { id: "trend", label: "趋势分析", icon: LineChart },
  { id: "history", label: "历史数据", icon: CalendarRange },
  { id: "revisions", label: "修订历史", icon: FileClock },
  { id: "documents", label: "相关文档", icon: BookOpenText },
  { id: "description", label: "指标说明", icon: Info },
];

function CapabilityUnavailable({ reason }: { reason?: string | null }) {
  return <div className="data-browser-unavailable"><AlertTriangle size={22} /><div><strong>该分析当前不可用</strong><p>{reason ?? "当前指标缺少满足条件的数据或许可。"}</p></div></div>;
}

export function AnalysisPanel({ state, item, capabilityState, analytics, analyticsLoading, analyticsError, onChange, onRetryAnalytics }: Props) {
  const tabList = useRef<HTMLDivElement>(null);
  const selectedId = item?.series.id ?? "";
  const availability = item?.availability;
  const catalogOnly = capabilityState === "catalog_only";
  const dataReady = capabilityState === "data_ready";
  const unavailableReason = catalogOnly && availability !== undefined && availability !== "available"
    ? catalogOnlyReason(availability)
    : undefined;
  const observations = useQuery({
    queryKey: ["data-browser-observations", selectedId, state.transform, state.start, state.end, state.data_as_of],
    queryFn: ({ signal }) => apiFetch<ObservationResponse>(`/series/${selectedId}/observations${queryString({ transform: state.transform, start: state.start, end: state.end, data_as_of: state.data_as_of })}`, { signal }),
    enabled: Boolean(selectedId) && dataReady && (state.tab === "trend" || state.tab === "history"),
    staleTime: 5 * 60_000,
    retry: (count, error) => !("status" in (error as object)) && count < 1,
  });
  const revisions = useQuery({ queryKey: ["data-browser-revisions", selectedId, state.data_as_of], queryFn: ({ signal }) => apiFetch<RevisionResponse>(`/series/${selectedId}/revisions${queryString({ data_as_of: state.data_as_of })}`, { signal }), enabled: Boolean(selectedId) && dataReady && state.tab === "revisions", staleTime: 5 * 60_000 });
  const documents = useQuery({ queryKey: ["data-browser-documents", selectedId], queryFn: ({ signal }) => apiFetch<{ items: DocumentSummary[]; total: number }>(`/documents${queryString({ series_id: selectedId, limit: 50 })}`, { signal }), enabled: Boolean(selectedId) && dataReady && state.tab === "documents", staleTime: 5 * 60_000 });
  const displayPoints = useMemo(() => downsampleForDisplay(observations.data?.data ?? []), [observations.data?.data]);
  const latest = observations.data?.data.at(-1);
  const first = observations.data?.data[0];

  function moveTab(direction: number) {
    const current = tabs.findIndex((tab) => tab.id === state.tab);
    const next = tabs[(current + direction + tabs.length) % tabs.length];
    onChange({ tab: next.id });
    requestAnimationFrame(() => tabList.current?.querySelector<HTMLButtonElement>(`[data-tab="${next.id}"]`)?.focus());
  }

  return <section className="data-browser-card data-browser-analysis-card" id="data-browser-analysis" aria-labelledby="analysis-title">
    <div className="data-browser-tabs" role="tablist" aria-label="指标分析" ref={tabList} onKeyDown={(event) => { if (event.key === "ArrowRight") moveTab(1); if (event.key === "ArrowLeft") moveTab(-1); }}>
      {tabs.map((tab) => <button key={tab.id} type="button" role="tab" data-tab={tab.id} aria-selected={state.tab === tab.id} tabIndex={state.tab === tab.id ? 0 : -1} onClick={() => onChange({ tab: tab.id })}><tab.icon size={14} />{tab.label}</button>)}
    </div>
    <div className="data-browser-analysis-content" role="tabpanel" aria-labelledby="analysis-title">
      {!selectedId && <div className="data-browser-inline-state"><strong>选择指标后开始分析</strong><span>趋势、历史、修订、文档和统计将在这里显示。</span></div>}
      {selectedId && catalogOnly && state.tab !== "description" && <CapabilityUnavailable reason={unavailableReason} />}
      {selectedId && dataReady && state.tab === "trend" && <div className="data-browser-trend-grid">
        <section className="data-browser-chart-panel"><header><div><h3 id="analysis-title">{item?.series.name_zh}（{state.transform}）</h3><p>{first?.period_start ?? "—"} 至 {latest?.period_start ?? "—"} · {observations.data?.data.length ?? 0} 个观测</p></div><div className="data-browser-range-buttons">{([["1年", 1], ["3年", 3], ["5年", 5], ["全部", 0]] as const).map(([label, years]) => <button type="button" className="btn" key={label} onClick={() => { const end = new Date(); const start = years ? new Date(end.getFullYear() - years, end.getMonth(), end.getDate()).toISOString().slice(0, 10) : ""; onChange({ start, end: "" }); }}>{label}</button>)}</div></header>
          {observations.isLoading ? <div className="skeleton h-[246px]" /> : observations.isError ? <div className="data-browser-inline-state"><strong>趋势加载失败</strong><span>{(observations.error as Error).message}</span><button className="btn" onClick={() => void observations.refetch()}>重试</button></div> : observations.data?.data.length ? <><p className="sr-only">趋势摘要：从 {first?.period_start} 的 {formatNumber(first?.value)} 变化到 {latest?.period_start} 的 {formatNumber(latest?.value)}。</p><TimeSeriesChart height={250} series={[{ name: item?.series.name_zh ?? "指标", data: displayPoints }]} /><details className="data-browser-chart-data"><summary>查看图表数据表</summary><div className="table-wrap"><table className="data-table"><thead><tr><th>参考期</th><th>数值</th></tr></thead><tbody>{observations.data.data.slice(-120).reverse().map((point) => <tr key={`${point.period_start}-${point.vintage_at}`}><td>{point.period_start}</td><td>{formatNumber(point.value)}</td></tr>)}</tbody></table></div></details></> : <div className="data-browser-inline-state"><strong>暂无趋势数据</strong><span>当前范围没有可展示观测。</span></div>}
        </section>
        <section className="data-browser-contribution-panel"><header><h3>贡献分析</h3><p>{analytics?.contributions.target_unit ?? "同一贡献口径"}</p></header>{analyticsLoading ? <div className="skeleton h-[250px]" /> : analyticsError ? <div className="data-browser-inline-state"><strong>分析加载失败</strong><span>{analyticsError.message}</span><button className="btn" onClick={onRetryAnalytics}><RefreshCw size={14} />重试</button></div> : analytics?.contributions.available ? <ContributionChart height={250} labels={analytics.contributions.periods.map((period) => period.period_start)} components={analytics.contributions.components.map((component) => ({ name: component.name_zh, values: component.values }))} /> : <CapabilityUnavailable reason={analytics?.contributions.reason ?? analytics?.capabilities.contributions.reason} />}</section>
        <section className="data-browser-statistics-panel"><header><h3>统计摘要</h3><p>当前范围</p></header>{analyticsLoading ? <div className="skeleton h-44" /> : analyticsError ? <CapabilityUnavailable reason={analyticsError.message} /> : <dl>{[["平均值",analytics?.statistics.mean],["中位数",analytics?.statistics.median],["最大值",analytics?.statistics.max],["最小值",analytics?.statistics.min],["标准差",analytics?.statistics.stddev],["当前分位数",analytics?.statistics.current_percentile == null ? null : `${analytics.statistics.current_percentile}%`]].map(([label,value]) => <div key={String(label)}><dt>{label}</dt><dd>{typeof value === "string" ? value : formatNumber(value)}</dd></div>)}</dl>}</section>
      </div>}
      {selectedId && dataReady && state.tab === "history" && (observations.isLoading ? <div className="skeleton h-72" /> : observations.isError ? <CapabilityUnavailable reason={(observations.error as Error).message} /> : <div className="data-browser-history-table table-wrap"><table className="data-table"><thead><tr><th>参考期</th><th>数值</th><th>状态</th><th>发布时间</th><th>数据版本</th></tr></thead><tbody>{[...(observations.data?.data ?? [])].reverse().map((point) => <tr key={`${point.period_start}-${point.vintage_at}`}><td>{point.period_start}</td><td>{formatNumber(point.value)}</td><td>{point.status}</td><td>{formatLocalDate(point.published_at, true)}</td><td>{formatLocalDate(point.vintage_at, true)}</td></tr>)}</tbody></table></div>)}
      {selectedId && dataReady && state.tab === "revisions" && (revisions.isLoading ? <div className="skeleton h-72" /> : revisions.isError ? <CapabilityUnavailable reason={(revisions.error as Error).message} /> : revisions.data?.items.length ? <div className="table-wrap"><table className="data-table"><thead><tr><th>参考期</th><th>版本数</th><th>上版值</th><th>最新版</th><th>修订幅度</th></tr></thead><tbody>{revisions.data.items.map((row) => <tr key={row.period_start}><td>{row.period_start}</td><td>{row.versions}</td><td>{formatNumber(row.previous_value)}</td><td>{formatNumber(row.latest_value)}</td><td>{formatNumber(row.absolute_revision)}</td></tr>)}</tbody></table></div> : <div className="data-browser-inline-state"><strong>暂无修订记录</strong><span>该指标当前没有多个可比较 vintage。</span></div>)}
      {selectedId && dataReady && state.tab === "documents" && (documents.isLoading ? <div className="skeleton h-72" /> : documents.isError ? <CapabilityUnavailable reason={(documents.error as Error).message} /> : documents.data?.items.length ? <div className="data-browser-document-list">{documents.data.items.map((document) => <a href={`/documents?document=${document.id}`} key={document.id}><strong>{document.title_zh ?? document.title}</strong><span>{document.provider_name} · {formatLocalDate(document.published_at)}</span><p>{document.summary_zh ?? "打开查看官方文档与引用位置。"}</p></a>)}</div> : <div className="data-browser-inline-state"><strong>暂无相关文档</strong><span>当前指标没有已建立关联的官方文档。</span></div>)}
      {selectedId && state.tab === "description" && <article className="data-browser-description"><h3>{item?.series.name_zh}</h3><p>{item && "description" in item.series ? item.series.description || "暂无指标说明。" : "暂无指标说明。"}</p><dl><div><dt>官方代码</dt><dd>{item?.series.canonical_code}</dd></div><div><dt>数据源</dt><dd>{item?.series.provider?.name ?? "—"}</dd></div><div><dt>更新时间</dt><dd>{formatLocalDate(item?.current?.published_at, true)}</dd></div><div><dt>数据快照</dt><dd>{state.data_as_of ? formatLocalDate(state.data_as_of, true) : "latest"}</dd></div></dl></article>}
    </div>
  </section>;
}
