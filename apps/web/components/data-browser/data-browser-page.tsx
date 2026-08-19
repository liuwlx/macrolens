"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, RefreshCw, Star } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { apiDownload, apiFetch, ApiError, queryString } from "@/lib/api";
import { formatTradingViewHistoryError } from "@/lib/sync-errors";
import type { AICapabilitiesResponse, Favorite, HistoryBatchPublic, JobPublic, SeriesAnalyticsResponse, SeriesBrowserItem, SeriesBrowserResponse, SeriesDetail, TaxonomyBrowserSeries } from "@/lib/types";
import { formatTradingViewSyncError } from "@/lib/sync-errors";

import { AnalysisPanel } from "./analysis-panel";
import { browserDataCapabilityState } from "./browser-availability";
import { BrowserDrawer } from "./browser-drawers";
import { BrowserFilterBar } from "./browser-filter-bar";
import { BrowserTable } from "./browser-table";
import { MetricTree } from "./metric-tree";
import { parseBrowserState, patchBrowserState, resetBrowserFilters, selectTaxonomyNode, serializeBrowserState, type BrowserSort, type BrowserState } from "./browser-query";
import { SeriesDetailPanel } from "./series-detail-panel";

type Drawer = "tree" | "filters" | "detail" | null;
type SyncState = "idle" | "running" | "success" | "error";

function historyBatchIsActive(batch: HistoryBatchPublic) {
  return batch.status === "queued" || batch.status === "running";
}

function formatHistoryBatchProgress(batch: HistoryBatchPublic) {
  const labels: Record<HistoryBatchPublic["status"], string> = {
    queued: "批量历史同步已排队",
    running: "批量历史同步进行中",
    succeeded: "批量历史同步完成",
    partial_failure: "批量历史同步部分失败",
    failed: "批量历史同步失败",
    empty: "批量历史同步无需处理",
  };
  return `${labels[batch.status]}：总数 ${batch.total}，排队 ${batch.queued}，运行 ${batch.running}，成功 ${batch.succeeded}，失败 ${batch.failed}，历史点 ${batch.staged_observation_count}`;
}

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
  const [syncState, setSyncState] = useState<SyncState>("idle");
  const [syncMessage, setSyncMessage] = useState("");
  const [historySyncState, setHistorySyncState] = useState<SyncState>("idle");
  const [historySyncMessage, setHistorySyncMessage] = useState("");
  const [historyBatch, setHistoryBatch] = useState<HistoryBatchPublic | null>(null);
  const [historyBatchPending, setHistoryBatchPending] = useState(false);
  const [historyBatchError, setHistoryBatchError] = useState("");
  const [historyBatchIdempotencyKey] = useState(() => `data-browser-history-${crypto.randomUUID()}`);
  const historyBatchMounted = useRef(true);
  const historyBatchPollCancel = useRef<(() => void) | null>(null);
  const historyBatchAbortController = useRef<AbortController | null>(null);
  const state = useMemo(() => parseBrowserState(searchParams), [searchParams]);
  const permissionKey = user ? `${user.id}:${user.role}` : "anonymous";

  useEffect(() => {
    historyBatchMounted.current = true;
    return () => {
      historyBatchMounted.current = false;
      historyBatchPollCancel.current?.();
      historyBatchAbortController.current?.abort();
    };
  }, []);

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
  const canSync = user?.role === "admin" && browserQuery.data?.data_mode === "live";
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
  const canSyncHistoryBatch = canSync && (
    state.provider === "TRADINGVIEW_WEB"
    || selectedItem?.series.provider?.code === "TRADINGVIEW_WEB"
  );
  const canSyncHistory = canSync && selectedItem?.availability === "available" && selectedItem.series.provider?.code === "TRADINGVIEW_WEB";
  const capabilityState = browserDataCapabilityState(
    selectedItem,
    browserQuery.data !== undefined && !browserQuery.isPlaceholderData,
  );
  const dataReady = capabilityState === "data_ready";
  const detailQuery = useQuery({ queryKey: ["data-browser-detail", permissionKey, state.series], queryFn: ({ signal }) => apiFetch<SeriesDetail>(`/series/${state.series}`, { signal }), enabled: Boolean(state.series) && dataReady, staleTime: 5 * 60_000, retry: shouldRetry });
  const analyticsQuery = useQuery({ queryKey: ["data-browser-analytics", permissionKey, state.series, state.transform, state.start, state.end, state.data_as_of], queryFn: ({ signal }) => apiFetch<SeriesAnalyticsResponse>(`/series/${state.series}/analytics${queryString({ transform: state.transform, start: state.start, end: state.end, data_as_of: state.data_as_of })}`, { signal }), enabled: Boolean(state.series) && dataReady, staleTime: 5 * 60_000, retry: shouldRetry });
  const aiQuery = useQuery({ queryKey: ["data-browser-ai-capability", permissionKey, state.series, state.data_as_of], queryFn: ({ signal }) => apiFetch<AICapabilitiesResponse>(`/ai/capabilities${queryString({ series_id: state.series, data_as_of: state.data_as_of })}`, { signal }), enabled: Boolean(state.series) && dataReady, staleTime: 5 * 60_000, retry: shouldRetry });
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

  async function syncTradingView() {
    if (!canSync || syncState === "running") return;
    setSyncState("running");
    setSyncMessage("");
    try {
      const providerCode = "TRADINGVIEW_WEB";
      const created = await apiFetch<JobPublic>(`/admin/providers/${providerCode}/sync`, {
        method: "POST",
        body: JSON.stringify({ mode: "latest" }),
      });
      let job = created;
      for (let attempt = 0; attempt < 180 && (job.status === "queued" || job.status === "running"); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        job = await apiFetch<JobPublic>(`/admin/jobs/${created.id}`);
      }
      if (job.status !== "succeeded") {
        throw new Error(job.last_error || "TradingView同步失败");
      }
      const result = job.result;
      const succeeded = Number(result.succeeded_count ?? result.inserted_count ?? 0);
      const failed = Number(result.failed_count ?? 0);
      setSyncState(failed ? "error" : "success");
      setSyncMessage(`同步完成：成功 ${succeeded} 项，失败 ${failed} 项`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["series-browser"] }),
        queryClient.invalidateQueries({ queryKey: ["taxonomy-children"] }),
        queryClient.invalidateQueries({ queryKey: ["data-browser-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["data-browser-analytics"] }),
      ]);
    } catch (error) {
      setSyncState("error");
      setSyncMessage(formatTradingViewSyncError(error));
    }
  }

  async function syncTradingViewHistory() {
    if (!canSyncHistory || !state.series || historySyncState === "running") return;
    setHistorySyncState("running");
    setHistorySyncMessage("");
    try {
      const providerCode = "TRADINGVIEW_WEB";
      const created = await apiFetch<JobPublic>(`/admin/providers/${providerCode}/series/${state.series}/history`, {
        method: "POST",
      });
      let job = created;
      for (let attempt = 0; attempt < 600 && (job.status === "queued" || job.status === "running"); attempt += 1) {
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
        job = await apiFetch<JobPublic>(`/admin/jobs/${created.id}`);
      }
      if (job.status !== "succeeded") {
        throw new Error(job.last_error || "未完成历史同步");
      }
      const result = job.result;
      setHistorySyncState("success");
      setHistorySyncMessage(`历史同步完成：新增 ${Number(result.inserted ?? 0)} 项，修订 ${Number(result.revised ?? 0)} 项，历史点 ${Number(result.staged_observation_count ?? result.observation_count ?? 0)} 项`);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["series-browser"] }),
        queryClient.invalidateQueries({ queryKey: ["data-browser-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["data-browser-observations"] }),
        queryClient.invalidateQueries({ queryKey: ["data-browser-analytics"] }),
      ]);
    } catch (error) {
      setHistorySyncState("error");
      setHistorySyncMessage(formatTradingViewHistoryError(error));
    }
  }

  async function syncTradingViewHistoryBatch() {
    if (!canSyncHistoryBatch || historyBatchPending) return;
    setHistoryBatchPending(true);
    setHistoryBatch(null);
    setHistoryBatchError("");
    const abortController = new AbortController();
    historyBatchAbortController.current = abortController;
    try {
      const providerCode = "TRADINGVIEW_WEB";
      let batch = await apiFetch<HistoryBatchPublic>(`/admin/providers/${providerCode}/history`, {
        method: "POST",
        body: JSON.stringify({ idempotency_key: historyBatchIdempotencyKey, limit: 500 }),
        signal: abortController.signal,
      });
      if (!historyBatchMounted.current) return;
      setHistoryBatch(batch);
      while (historyBatchIsActive(batch)) {
        const continuePolling = await new Promise<boolean>((resolve) => {
          const timeoutId = window.setTimeout(() => {
            historyBatchPollCancel.current = null;
            resolve(true);
          }, 2000);
          historyBatchPollCancel.current = () => {
            window.clearTimeout(timeoutId);
            historyBatchPollCancel.current = null;
            resolve(false);
          };
        });
        if (!continuePolling || !historyBatchMounted.current) return;
        batch = await apiFetch<HistoryBatchPublic>(`/admin/providers/${providerCode}/history/${batch.batch_id}`, {
          signal: abortController.signal,
        });
        if (!historyBatchMounted.current) return;
        setHistoryBatch(batch);
      }
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["series-browser"] }),
        queryClient.invalidateQueries({ queryKey: ["data-browser-detail"] }),
        queryClient.invalidateQueries({ queryKey: ["data-browser-observations"] }),
        queryClient.invalidateQueries({ queryKey: ["data-browser-analytics"] }),
        queryClient.invalidateQueries({ queryKey: ["taxonomy-children"] }),
      ]);
    } catch (error) {
      if (historyBatchMounted.current) setHistoryBatchError(formatTradingViewHistoryError(error));
    } finally {
      if (historyBatchAbortController.current === abortController) {
        historyBatchAbortController.current = null;
      }
      if (historyBatchMounted.current) setHistoryBatchPending(false);
    }
  }
  const closeDrawer = useCallback(() => setDrawer(null), []);

  const filterProps = { state, facets: browserQuery.data?.facets, onChange: updateState, onReset: () => updateState(resetBrowserFilters(state)), onOpenFilters: () => setDrawer("filters"), onOpenTree: () => setDrawer("tree"), onOpenDetail: () => setDrawer("detail") };
  const detailProps = { item: selectedItem, detail: detailQuery.data, analytics: analyticsQuery.data, ai: aiQuery.data, isLoading: detailQuery.isLoading, isFavorite: Boolean(selectedFavorite), favoritePending: favoriteMutation.isPending, readOnlyReason: demoReadOnlyReason, onFavorite: () => { if (!isDemo) favoriteMutation.mutate(); }, onHistory: showHistory, canSyncHistory, onSyncHistory: () => void syncTradingViewHistory(), historySyncPending: historySyncState === "running", historySyncMessage, onCompare: () => router.push(`/compare?series=${encodeURIComponent(state.series)}`), onExport: exportSelected, onAI: () => { if (!isDemo) router.push(`/ai?series=${encodeURIComponent(state.series)}&data_as_of=${encodeURIComponent(state.data_as_of)}`); } };

  return <div className="data-browser-page">
    {isDemo && <div className="data-browser-demo-banner" role="note"><strong>DEMO 演示数据</strong><span>当前页面使用固定演示快照；趋势、历史、修订、统计、只读比较和 CSV 导出可用，收藏、工作台与 AI 写入已禁用。</span></div>}
    <header className="data-browser-page-header"><div><div className="data-browser-title"><Database size={22} /><h1>数据浏览器 / 指标树与明细表</h1></div><p>浏览、筛选并分析宏观经济指标，支持多层级指标分类与历史修订查看。</p></div><div className="data-browser-header-actions"><span>当前位置：宏观经济数据 / {selectedItem?.series.theme ?? "全部主题"} / {selectedItem?.series.name_zh ?? "请选择指标"}</span>{canSyncHistoryBatch && <button className="btn" type="button" onClick={() => void syncTradingViewHistoryBatch()} disabled={historyBatchPending} title="同步 TradingView 指标的历史数据"><RefreshCw size={15} className={historyBatchPending ? "animate-spin" : ""} />{historyBatchPending ? "批量同步中…" : "批量同步历史"}</button>}{canSync && <button className="btn btn-primary" type="button" onClick={() => void syncTradingView()} disabled={syncState === "running"}><RefreshCw size={15} className={syncState === "running" ? "animate-spin" : ""} />{syncState === "running" ? "同步中…" : "数据同步"}</button>}<button className={`btn ${selectedFavorite ? "btn-primary" : ""}`} type="button" onClick={() => { if (!isDemo) favoriteMutation.mutate(); }} disabled={!state.series || favoriteMutation.isPending || isDemo} title={demoReadOnlyReason}><Star size={15} fill={selectedFavorite ? "currentColor" : "none"} />{selectedFavorite ? "已收藏" : "收藏该指标"}</button></div></header>
    {(historyBatch || historyBatchError) && <div className={`data-browser-sync-status ${historyBatchError || historyBatch?.status === "failed" || historyBatch?.status === "partial_failure" ? "is-error" : ""}`} role="status">{historyBatchError ? `批量${historyBatchError}` : historyBatch ? formatHistoryBatchProgress(historyBatch) : null}</div>}
    {syncMessage && <div className={`data-browser-sync-status ${syncState === "error" ? "is-error" : ""}`} role="status">{syncMessage}</div>}
    <BrowserFilterBar {...filterProps} />
    <div className="data-browser-workspace">
      <MetricTree state={state} onNode={(node) => updateState(selectTaxonomyNode(state, node))} onSeries={selectSeries} />
      <BrowserTable state={state} data={browserQuery.data} isLoading={browserQuery.isLoading} isFetching={browserQuery.isFetching} error={browserQuery.error as Error | null} onRetry={() => void browserQuery.refetch()} onRefresh={refreshAll} onExport={exportBrowser} onSelect={selectItem} onSort={sort} onPage={(page) => updateState({ page })} />
      <SeriesDetailPanel {...detailProps} />
      <AnalysisPanel state={state} item={selectedItem} capabilityState={capabilityState} analytics={analyticsQuery.data} analyticsLoading={analyticsQuery.isLoading} analyticsError={analyticsQuery.error as Error | null} onChange={updateState} onRetryAnalytics={() => void analyticsQuery.refetch()} />
    </div>
    <BrowserDrawer open={drawer} title={drawer === "tree" ? "指标树" : drawer === "filters" ? "筛选条件" : "指标详情"} onClose={closeDrawer}>{drawer === "tree" ? <MetricTree state={state} onNode={(node) => { updateState(selectTaxonomyNode(state, node)); closeDrawer(); }} onSeries={(series, node) => { selectSeries(series, node); closeDrawer(); }} /> : drawer === "filters" ? <BrowserFilterBar {...filterProps} /> : <SeriesDetailPanel {...detailProps} />}</BrowserDrawer>
    {availableSnapshot && <div className="data-browser-new-snapshot" role="status"><span>检测到新数据快照，不会自动替换当前研究上下文。</span><button className="btn btn-primary" type="button" onClick={() => { updateState({ data_as_of: availableSnapshot }); setAvailableSnapshot(""); }}>切换到新数据</button><button className="btn btn-ghost" type="button" onClick={() => setAvailableSnapshot("")}>稍后</button></div>}
    {browserQuery.isFetching && !browserQuery.isLoading && <div className="data-browser-updating" role="status"><RefreshCw className="animate-spin" size={14} />正在刷新当前快照</div>}
  </div>;
}
