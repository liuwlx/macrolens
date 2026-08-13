"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, RefreshCw, Star } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { apiDownload, apiFetch, ApiError, queryString } from "@/lib/api";
import type { AICapabilitiesResponse, Favorite, SeriesAnalyticsResponse, SeriesBrowserItem, SeriesBrowserResponse, SeriesDetail, TaxonomyBrowserSeries } from "@/lib/types";

import { AnalysisPanel } from "./analysis-panel";
import { isCatalogOnlyAvailability } from "./browser-availability";
import { BrowserDrawer } from "./browser-drawers";
import { BrowserFilterBar } from "./browser-filter-bar";
import { BrowserTable } from "./browser-table";
import { MetricTree } from "./metric-tree";
import { parseBrowserState, patchBrowserState, resetBrowserFilters, serializeBrowserState, type BrowserSort, type BrowserState } from "./browser-query";
import { SeriesDetailPanel } from "./series-detail-panel";

type Drawer = "tree" | "filters" | "detail" | null;

function shouldRetry(count: number, error: Error) {
  if (error instanceof ApiError && error.status < 500) return false;
  return count < 1;
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function markDemoFilename(filename: string) {
  return filename.endsWith(".demo.csv") ? filename : filename.replace(/\.csv$/i, ".demo.csv");
}

export function DataBrowserPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const [drawer, setDrawer] = useState<Drawer>(null);
  const [availableSnapshot, setAvailableSnapshot] = useState("");
  const state = useMemo(() => parseBrowserState(searchParams), [searchParams]);
  const permissionKey = user ? `${user.id}:${user.role}` : "anonymous";

  const updateState = useCallback((patch: Partial<BrowserState>, mode: "replace" | "push" = "replace") => {
    const next = patchBrowserState(state, patch);
    const params = serializeBrowserState(next, new URLSearchParams(searchParams.toString()));
    const href = `/data${params.size ? `?${params.toString()}` : ""}`;
    router[mode](href, { scroll: false });
  }, [router, searchParams, state]);

  const browserQuery = useQuery({
    queryKey: ["series-browser", permissionKey, state.q, state.node, state.provider, state.theme, state.frequency, state.unit, state.seasonal_adjustment, state.published_from, state.published_to, state.page, state.sort, state.order, state.data_as_of],
    queryFn: ({ signal }) => apiFetch<SeriesBrowserResponse>(`/series/browser${queryString({ q: state.q, node_id: state.node, provider: state.provider, theme: state.theme, frequency: state.frequency, unit: state.unit, seasonal_adjustment: state.seasonal_adjustment, published_from: state.published_from, published_to: state.published_to, sort: state.sort, order: state.order, limit: 20, offset: (state.page - 1) * 20, data_as_of: state.data_as_of })}`, { signal }),
    placeholderData: keepPreviousData,
    staleTime: 5 * 60_000,
    retry: shouldRetry,
  });
  const isDemo = browserQuery.data?.data_mode === "demo";
  const demoReadOnlyReason = isDemo ? "DEMO 演示数据为只读，不能收藏、写入工作台或加入 AI 上下文" : undefined;

  useEffect(() => {
    if (!browserQuery.data || browserQuery.isPlaceholderData) return;
    const items = browserQuery.data.items;
    const selectedExists = state.series && items.some((item) => item.series.id === state.series);
    const nextSeries = selectedExists ? state.series : items[0]?.series.id ?? "";
    const hasObservations = items.some((item) => item.availability === "available" && item.current !== null);
    const nextSnapshot = hasObservations
      ? browserQuery.data.data_mode === "demo" ? browserQuery.data.data_as_of : state.data_as_of || browserQuery.data.data_as_of
      : state.data_as_of;
    if (nextSeries !== state.series || nextSnapshot !== state.data_as_of) updateState({ series: nextSeries, data_as_of: nextSnapshot });
  }, [browserQuery.data, browserQuery.isPlaceholderData, state.series, state.data_as_of, updateState]);

  const selectedItem = browserQuery.data?.items.find((item) => item.series.id === state.series);
  const catalogOnly = isCatalogOnlyAvailability(selectedItem?.availability);
  const detailQuery = useQuery({ queryKey: ["data-browser-detail", permissionKey, state.series], queryFn: ({ signal }) => apiFetch<SeriesDetail>(`/series/${state.series}`, { signal }), enabled: Boolean(state.series) && !catalogOnly, staleTime: 5 * 60_000, retry: shouldRetry });
  const analyticsQuery = useQuery({ queryKey: ["data-browser-analytics", permissionKey, state.series, state.transform, state.start, state.end, state.data_as_of], queryFn: ({ signal }) => apiFetch<SeriesAnalyticsResponse>(`/series/${state.series}/analytics${queryString({ transform: state.transform, start: state.start, end: state.end, data_as_of: state.data_as_of })}`, { signal }), enabled: Boolean(state.series) && !catalogOnly, staleTime: 5 * 60_000, retry: shouldRetry });
  const aiQuery = useQuery({ queryKey: ["data-browser-ai-capability", permissionKey, state.series, state.data_as_of], queryFn: ({ signal }) => apiFetch<AICapabilitiesResponse>(`/ai/capabilities${queryString({ series_id: state.series, data_as_of: state.data_as_of })}`, { signal }), enabled: Boolean(state.series) && !catalogOnly, staleTime: 5 * 60_000, retry: shouldRetry });
  const favoritesQuery = useQuery({ queryKey: ["favorites", permissionKey], queryFn: ({ signal }) => apiFetch<Favorite[]>("/me/favorites", { signal }), staleTime: 5 * 60_000, retry: shouldRetry });
  const selectedFavorite = favoritesQuery.data?.find((favorite) => favorite.object_type === "series" && favorite.object_id === state.series);
  const favoriteMutation = useMutation({ mutationFn: () => selectedFavorite ? apiFetch(`/me/favorites/${selectedFavorite.id}`, { method: "DELETE" }) : apiFetch("/me/favorites", { method: "POST", body: JSON.stringify({ object_type: "series", object_id: state.series, group_name: "重点指标" }) }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["favorites", permissionKey] }) });

  function selectItem(item: SeriesBrowserItem) {
    const start = state.start || new Date(new Date().setFullYear(new Date().getFullYear() - 5)).toISOString().slice(0, 10);
    updateState({ series: item.series.id, transform: item.series.default_transform || "level", start }, "push");
  }
  function selectSeries(series: TaxonomyBrowserSeries, node: string | null) { updateState({ series: series.id, node: node ?? "", q: series.canonical_code, page: 1 }, "push"); }
  function sort(sort: BrowserSort) { updateState({ sort, order: state.sort === sort && state.order === "asc" ? "desc" : "asc" }); }
  function exportPath(path: string, fallback: string) { void apiDownload(path).then(({ blob, filename }) => saveBlob(blob, isDemo ? markDemoFilename(filename ?? fallback) : filename ?? fallback)); }
  function exportBrowser() { exportPath(`/series/browser/export${queryString({ q: state.q, node_id: state.node, provider: state.provider, theme: state.theme, frequency: state.frequency, unit: state.unit, seasonal_adjustment: state.seasonal_adjustment, published_from: state.published_from, published_to: state.published_to, sort: state.sort, order: state.order, data_as_of: state.data_as_of })}`, "macrolens-data-browser.csv"); }
  function exportSelected() { if (state.series) exportPath(`/series/${state.series}/export${queryString({ transform: state.transform, start: state.start, end: state.end, data_as_of: state.data_as_of })}`, `${detailQuery.data?.canonical_code ?? "macrolens-series"}.csv`); }
  function showHistory() { updateState({ tab: "history" }); requestAnimationFrame(() => document.getElementById("data-browser-analysis")?.scrollIntoView({ behavior: "smooth", block: "start" })); }
  async function refreshAll() {
    const latest = await queryClient.fetchQuery({
      queryKey: ["series-browser-latest-check", permissionKey, state.q, state.node, state.provider, state.theme, state.frequency, state.unit, state.seasonal_adjustment, state.published_from, state.published_to, state.page, state.sort, state.order],
      queryFn: ({ signal }) => apiFetch<SeriesBrowserResponse>(`/series/browser${queryString({ q: state.q, node_id: state.node, provider: state.provider, theme: state.theme, frequency: state.frequency, unit: state.unit, seasonal_adjustment: state.seasonal_adjustment, published_from: state.published_from, published_to: state.published_to, sort: state.sort, order: state.order, limit: 20, offset: (state.page - 1) * 20 })}`, { signal }),
      staleTime: 0,
    });
    if (latest.data_as_of !== state.data_as_of) setAvailableSnapshot(latest.data_as_of);
  }
  const closeDrawer = useCallback(() => setDrawer(null), []);

  const filterProps = { state, facets: browserQuery.data?.facets, onChange: updateState, onReset: () => updateState(resetBrowserFilters(state)), onOpenFilters: () => setDrawer("filters"), onOpenTree: () => setDrawer("tree"), onOpenDetail: () => setDrawer("detail") };
  const detailProps = { item: selectedItem, detail: detailQuery.data, analytics: analyticsQuery.data, ai: aiQuery.data, isLoading: detailQuery.isLoading, isFavorite: Boolean(selectedFavorite), favoritePending: favoriteMutation.isPending, readOnlyReason: demoReadOnlyReason, onFavorite: () => { if (!isDemo) favoriteMutation.mutate(); }, onHistory: showHistory, onCompare: () => router.push(`/compare?series=${encodeURIComponent(state.series)}`), onExport: exportSelected, onAI: () => { if (!isDemo) router.push(`/ai?series=${encodeURIComponent(state.series)}&data_as_of=${encodeURIComponent(state.data_as_of)}`); } };

  return <div className="data-browser-page">
    {isDemo && <div className="data-browser-demo-banner" role="note"><strong>DEMO 演示数据</strong><span>当前页面使用固定演示快照；趋势、历史、修订、统计、只读比较和 CSV 导出可用，收藏、工作台与 AI 写入已禁用。</span></div>}
    <header className="data-browser-page-header"><div><div className="data-browser-title"><Database size={22} /><h1>数据浏览器 / 指标树与明细表</h1></div><p>浏览、筛选并分析宏观经济指标，支持多层级指标分类与历史修订查看。</p></div><div className="data-browser-header-actions"><span>当前位置：宏观经济数据 / {selectedItem?.series.theme ?? "全部主题"} / {selectedItem?.series.name_zh ?? "请选择指标"}</span><button className={`btn ${selectedFavorite ? "btn-primary" : ""}`} type="button" onClick={() => { if (!isDemo) favoriteMutation.mutate(); }} disabled={!state.series || favoriteMutation.isPending || isDemo} title={demoReadOnlyReason}><Star size={15} fill={selectedFavorite ? "currentColor" : "none"} />{selectedFavorite ? "已收藏" : "收藏该指标"}</button></div></header>
    <BrowserFilterBar {...filterProps} />
    <div className="data-browser-workspace">
      <MetricTree state={state} onNode={(node) => updateState({ node })} onSeries={selectSeries} />
      <BrowserTable state={state} data={browserQuery.data} isLoading={browserQuery.isLoading} isFetching={browserQuery.isFetching} error={browserQuery.error as Error | null} onRetry={() => void browserQuery.refetch()} onRefresh={refreshAll} onExport={exportBrowser} onSelect={selectItem} onSort={sort} onPage={(page) => updateState({ page })} />
      <SeriesDetailPanel {...detailProps} />
      <AnalysisPanel state={state} item={selectedItem} analytics={analyticsQuery.data} analyticsLoading={analyticsQuery.isLoading} analyticsError={analyticsQuery.error as Error | null} onChange={updateState} onRetryAnalytics={() => void analyticsQuery.refetch()} />
    </div>
    <BrowserDrawer open={drawer} title={drawer === "tree" ? "指标树" : drawer === "filters" ? "筛选条件" : "指标详情"} onClose={closeDrawer}>{drawer === "tree" ? <MetricTree state={state} onNode={(node) => { updateState({ node }); closeDrawer(); }} onSeries={(series, node) => { selectSeries(series, node); closeDrawer(); }} /> : drawer === "filters" ? <BrowserFilterBar {...filterProps} /> : <SeriesDetailPanel {...detailProps} />}</BrowserDrawer>
    {availableSnapshot && <div className="data-browser-new-snapshot" role="status"><span>检测到新数据快照，不会自动替换当前研究上下文。</span><button className="btn btn-primary" type="button" onClick={() => { updateState({ data_as_of: availableSnapshot }); setAvailableSnapshot(""); }}>切换到新数据</button><button className="btn btn-ghost" type="button" onClick={() => setAvailableSnapshot("")}>稍后</button></div>}
    {browserQuery.isFetching && !browserQuery.isLoading && <div className="data-browser-updating" role="status"><RefreshCw className="animate-spin" size={14} />正在刷新当前快照</div>}
  </div>;
}
