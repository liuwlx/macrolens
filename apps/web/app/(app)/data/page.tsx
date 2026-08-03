"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, Search, Star } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useMemo, useState } from "react";

import { TimeSeriesChart } from "@/components/chart";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch, queryString } from "@/lib/api";
import type { ObservationResponse, SeriesDetail, SeriesSummary } from "@/lib/types";

const transforms = [
  ["level", "原始值"], ["mom", "环比"], ["yoy", "同比"], ["annualized_3m", "3个月年化"], ["annualized_6m", "6个月年化"], ["zscore", "标准分数"],
] as const;

function DataContent() {
  const params = useSearchParams();
  const router = useRouter();
  const queryParam = params.get("q") ?? "";
  const seriesParam = params.get("series") ?? "";
  const [query, setQuery] = useState(queryParam);
  const [theme, setTheme] = useState("");
  const [selectedId, setSelectedId] = useState(seriesParam);
  const [transform, setTransform] = useState("level");

  useEffect(() => setQuery(queryParam), [queryParam]);
  useEffect(() => {
    if (seriesParam) setSelectedId(seriesParam);
  }, [seriesParam]);

  const seriesQuery = useQuery({
    queryKey: ["series", query, theme],
    queryFn: () => apiFetch<{ items: SeriesSummary[]; total: number }>(`/series${queryString({ q: query, theme, limit: 200 })}`),
  });
  useEffect(() => {
    if (!selectedId && seriesQuery.data?.items[0]) setSelectedId(seriesQuery.data.items[0].id);
  }, [seriesQuery.data, selectedId]);
  const detailQuery = useQuery({ queryKey: ["series-detail", selectedId], queryFn: () => apiFetch<SeriesDetail>(`/series/${selectedId}`), enabled: !!selectedId });
  const observationQuery = useQuery({ queryKey: ["observations", selectedId, transform], queryFn: () => apiFetch<ObservationResponse>(`/series/${selectedId}/observations${queryString({ transform })}`), enabled: !!selectedId });
  const revisionQuery = useQuery({ queryKey: ["revisions", selectedId], queryFn: () => apiFetch<{ items: Array<Record<string, unknown>> }>(`/series/${selectedId}/revisions`), enabled: !!selectedId });
  const favorite = useMutation({ mutationFn: () => apiFetch("/me/favorites", { method: "POST", body: JSON.stringify({ object_type: "series", object_id: selectedId, group_name: "重点指标" }) }) });

  function chooseSeries(id: string) {
    setSelectedId(id);
    const next = new URLSearchParams(params.toString());
    next.set("series", id);
    router.replace(`/data?${next.toString()}`);
  }

  function downloadCsv() {
    if (!observationQuery.data?.meta.license?.download_allowed) return;
    const lines = ["period_start,period_end,value,status,vintage_at", ...observationQuery.data.data.map((point) => [point.period_start, point.period_end, point.value ?? "", point.status, point.vintage_at].join(","))];
    const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${observationQuery.data.series.canonical_code}-${transform}.csv`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  const themes = useMemo(() => Array.from(new Set((seriesQuery.data?.items ?? []).map((item) => item.theme))), [seriesQuery.data]);

  return (
    <div>
      <PageHeader title="数据总览 / 指标与时间序列" description="搜索指标、查看历史数据与修订，并追溯到官方数据源。" actions={<><button className="btn" onClick={() => favorite.mutate()} disabled={!selectedId || favorite.isPending}><Star size={16}/>收藏</button><button className="btn" onClick={downloadCsv} disabled={!observationQuery.data?.meta.license?.download_allowed} title={observationQuery.data?.meta.license?.download_allowed ? "导出当前时间序列" : "当前数据许可不允许下载"}><Download size={16}/>导出CSV</button></>} />
      <div className="mb-4 grid gap-3 md:grid-cols-[1fr_220px]">
        <label className="relative"><Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><input className="input !pl-10" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索核心PCE、非农、利率或官方序列号"/></label>
        <select className="select" value={theme} onChange={(event) => setTheme(event.target.value)}><option value="">全部主题</option>{themes.map((item) => <option key={item}>{item}</option>)}</select>
      </div>
      <div className="grid gap-5 xl:grid-cols-[330px_minmax(0,1fr)_310px]">
        <section className="card max-h-[calc(100vh-190px)] overflow-hidden"><div className="card-header"><div><h2 className="section-title">指标目录</h2><p className="mt-1 text-xs text-slate-500">{seriesQuery.data?.total ?? 0} 条</p></div></div><div className="max-h-[calc(100vh-270px)] overflow-y-auto p-2">{seriesQuery.isLoading ? <div className="space-y-2 p-2">{Array.from({length:8}).map((_,i)=><div key={i} className="skeleton h-14"/>)}</div> : seriesQuery.data?.items.length ? seriesQuery.data.items.map((item) => <button key={item.id} className={`mb-1 w-full rounded-lg p-3 text-left transition ${selectedId === item.id ? "bg-blue-50 ring-1 ring-blue-200" : "hover:bg-slate-50"}`} onClick={() => chooseSeries(item.id)}><div className="truncate text-sm font-semibold">{item.name_zh}</div><div className="mt-1 flex items-center justify-between gap-2 text-xs text-slate-500"><span>{item.canonical_code}</span><span>{item.frequency}</span></div></button>) : <div className="p-8 text-center text-sm text-slate-500">没有匹配指标</div>}</div></section>
        <section className="min-w-0 space-y-5">
          {!selectedId ? <EmptyState title="选择一个指标" description="从左侧指标目录选择要查看的时间序列。"/> : observationQuery.isLoading ? <LoadingBlock/> : observationQuery.isError ? <ErrorState message={(observationQuery.error as Error).message} retry={() => void observationQuery.refetch()}/> : observationQuery.data ? <>
            <div className="card"><div className="card-header flex-wrap"><div><h2 className="section-title">{observationQuery.data.series.name_zh}</h2><p className="mt-1 text-xs text-slate-500">{observationQuery.data.series.canonical_code} · 数据截至 {new Date(observationQuery.data.meta.data_as_of).toLocaleString("zh-CN")}</p></div><div className="flex flex-wrap gap-2">{transforms.map(([value,label])=><button key={value} className={`btn !min-h-8 !px-3 !text-xs ${transform===value?"btn-primary":""}`} onClick={()=>setTransform(value)}>{label}</button>)}</div></div><div className="card-body"><TimeSeriesChart series={[{name:observationQuery.data.series.name_zh,data:observationQuery.data.data}]} height={390}/></div></div>
            <div className="card"><div className="card-header"><h2 className="section-title">历史数据</h2><span className="text-xs text-slate-500">{observationQuery.data.data.length} 期</span></div><div className="table-wrap max-h-[420px]"><table className="data-table"><thead><tr><th>参考期</th><th>数值</th><th>状态</th><th>发布时间</th><th>数据版本</th></tr></thead><tbody>{[...observationQuery.data.data].reverse().map((point)=><tr key={`${point.period_start}-${point.vintage_at}`}><td>{point.period_start}</td><td className="font-semibold">{point.value == null ? "—" : Number(point.value).toLocaleString(undefined,{maximumFractionDigits:4})}</td><td><span className={`badge ${point.status==="revised"?"badge-yellow":"badge-green"}`}>{point.status}</span></td><td>{point.published_at ? new Date(point.published_at).toLocaleString("zh-CN") : "—"}</td><td>{new Date(point.vintage_at).toLocaleString("zh-CN")}</td></tr>)}</tbody></table></div></div>
          </> : null}
        </section>
        <aside className="space-y-5">
          <div className="card"><div className="card-header"><h2 className="section-title">指标信息</h2></div><div className="card-body space-y-4 text-sm">{detailQuery.data ? <><div><div className="text-xs text-slate-500">最新值</div><div className="mt-1 text-3xl font-bold">{detailQuery.data.latest_value == null ? "—" : Number(detailQuery.data.latest_value).toLocaleString(undefined,{maximumFractionDigits:4})}</div><div className="mt-1 text-xs text-slate-500">{detailQuery.data.latest_period} · {detailQuery.data.unit_label_zh}</div></div>{[["来源",detailQuery.data.provider?.name],["频率",detailQuery.data.frequency],["季调",detailQuery.data.seasonal_adjustment],["地理",detailQuery.data.geography_code],["首次期间",detailQuery.data.first_period]].map(([label,value])=><div key={label as string} className="flex justify-between gap-3 border-t border-slate-100 pt-3"><span className="text-slate-500">{label}</span><span className="text-right font-medium">{value || "—"}</span></div>)}<p className="border-t border-slate-100 pt-3 leading-6 text-slate-600">{detailQuery.data.description || "暂无指标说明。"}</p></> : <div className="skeleton h-56"/>}</div></div>
          {observationQuery.data?.meta.license && <div className="card"><div className="card-header"><h2 className="section-title">许可与署名</h2></div><div className="card-body space-y-2 text-sm"><div className="flex justify-between"><span className="text-slate-500">网页展示</span><span className={observationQuery.data.meta.license.display_allowed?"text-emerald-700":"text-red-600"}>{observationQuery.data.meta.license.display_allowed?"允许":"禁止"}</span></div><div className="flex justify-between"><span className="text-slate-500">数据下载</span><span className={observationQuery.data.meta.license.download_allowed?"text-emerald-700":"text-amber-700"}>{observationQuery.data.meta.license.download_allowed?"允许":"受限"}</span></div>{observationQuery.data.meta.license.attribution_text&&<p className="border-t border-slate-100 pt-2 text-xs leading-5 text-slate-500">{observationQuery.data.meta.license.attribution_text}</p>}</div></div>}
          <div className="card"><div className="card-header"><h2 className="section-title">修订概览</h2></div><div className="card-body">{revisionQuery.data?.items?.length ? <div className="space-y-3 text-sm">{revisionQuery.data.items.slice(-8).reverse().map((item,index)=><div key={index} className="flex items-center justify-between gap-2"><span>{String(item.period_start)}</span><span className="badge badge-yellow">{String(item.versions)} 个版本</span></div>)}</div> : <p className="text-sm text-slate-500">暂无可显示的修订记录。</p>}</div></div>
          {observationQuery.data?.meta.lineage && <div className="card"><div className="card-header"><h2 className="section-title">数据血缘</h2></div><div className="card-body space-y-2 text-sm"><div><span className="text-slate-500">Provider：</span>{observationQuery.data.meta.lineage.provider}</div><div><span className="text-slate-500">Dataset：</span>{observationQuery.data.meta.lineage.dataset}</div><div><span className="text-slate-500">外部编号：</span>{observationQuery.data.meta.lineage.provider_series_id || "元数据行映射"}</div></div></div>}
        </aside>
      </div>
    </div>
  );
}

export default function DataPage() { return <Suspense fallback={<LoadingBlock/>}><DataContent/></Suspense>; }
