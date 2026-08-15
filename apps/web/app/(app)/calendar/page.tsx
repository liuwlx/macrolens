"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { addDays, format } from "date-fns";
import { BellPlus, CalendarClock, ExternalLink, Filter, Sparkles } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { BarChart } from "@/components/chart";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch, queryString } from "@/lib/api";
import type { ReleaseEvent, ReleaseEventDetail } from "@/lib/types";

const fmt = (value: unknown, unit?: string | null) =>
  value == null ? "—" : `${Number(value).toLocaleString(undefined, { maximumFractionDigits: 3 })}${unit ?? ""}`;

function CalendarContent() {
  const searchParams = useSearchParams();
  const initialEvent = searchParams.get("event") ?? "";
  const now = new Date();
  const [start, setStart] = useState(format(addDays(now, -7), "yyyy-MM-dd"));
  const [end, setEnd] = useState(format(addDays(now, 30), "yyyy-MM-dd"));
  const [importance, setImportance] = useState(1);
  const [provider, setProvider] = useState("");
  const [selectedIdOverride, setSelectedId] = useState(initialEvent);

  const eventsQuery = useQuery({
    queryKey: ["release-events", start, end, importance, provider],
    queryFn: () => apiFetch<{ items: ReleaseEvent[]; total: number }>(`/release-events${queryString({ start, end, country: "US", importance_min: importance, provider, limit: 300 })}`),
  });
  const selectedId = selectedIdOverride || eventsQuery.data?.items[0]?.id || "";
  const detailQuery = useQuery({
    queryKey: ["release-event", selectedId],
    queryFn: () => apiFetch<ReleaseEventDetail>(`/release-events/${selectedId}`),
    enabled: Boolean(selectedId),
  });
  const alertMutation = useMutation({
    mutationFn: () => apiFetch("/me/alerts", {
      method: "POST",
      body: JSON.stringify({
        name: `${detailQuery.data?.title_zh ?? "宏观数据"}发布提醒`,
        alert_type: "release_reminder",
        target_type: "release_event",
        target_id: selectedId,
        rule: { minutes_before: 30 },
        channels: ["in_app", "email"],
      }),
    }),
  });

  const grouped = useMemo(() => {
    const result = new Map<string, ReleaseEvent[]>();
    for (const event of eventsQuery.data?.items ?? []) {
      const day = format(new Date(event.scheduled_at), "yyyy-MM-dd");
      result.set(day, [...(result.get(day) ?? []), event]);
    }
    return result;
  }, [eventsQuery.data]);

  const forecastLabels = detailQuery.data?.forecasts.slice().reverse().map((item) => format(new Date(item.observed_at), "MM-dd")) ?? [];
  const forecastValues = detailQuery.data?.forecasts.slice().reverse().map((item) => Number(item.consensus_value ?? 0)) ?? [];

  return (
    <div>
      <PageHeader
        title="发布日历 / 宏观事件与数据发布"
        description="追踪官方发布时间、市场预期、历史修订和数据公布后的资产反应。"
        actions={<button className="btn btn-primary" disabled={!selectedId || alertMutation.isPending} onClick={() => alertMutation.mutate()}><BellPlus size={16}/>{alertMutation.isSuccess ? "已创建提醒" : "订阅提醒"}</button>}
      />
      <div className="card mb-5 p-4">
        <div className="grid gap-3 md:grid-cols-[180px_180px_150px_180px_1fr]">
          <label className="text-xs text-slate-500">开始日期<input className="input mt-1" type="date" value={start} onChange={(event) => setStart(event.target.value)}/></label>
          <label className="text-xs text-slate-500">结束日期<input className="input mt-1" type="date" value={end} onChange={(event) => setEnd(event.target.value)}/></label>
          <label className="text-xs text-slate-500">最低重要性<select className="select mt-1" value={importance} onChange={(event) => setImportance(Number(event.target.value))}><option value={1}>全部</option><option value={2}>★★ 以上</option><option value={3}>★★★ 以上</option><option value={4}>★★★★ 以上</option></select></label>
          <label className="text-xs text-slate-500">来源机构<select className="select mt-1" value={provider} onChange={(event) => setProvider(event.target.value)}><option value="">全部来源</option><option>BEA</option><option>BLS</option><option>FEDERAL_RESERVE</option><option>CENSUS</option><option>DOL</option></select></label>
          <div className="flex items-end"><div className="flex h-10 w-full items-center gap-2 rounded-lg bg-slate-50 px-3 text-sm text-slate-500"><Filter size={16}/>共 {eventsQuery.data?.total ?? 0} 个事件，时间按浏览器时区显示</div></div>
        </div>
      </div>

      {eventsQuery.isLoading ? <LoadingBlock/> : eventsQuery.isError ? <ErrorState message={(eventsQuery.error as Error).message} retry={() => void eventsQuery.refetch()}/> : !eventsQuery.data?.items.length ? <EmptyState title="该日期范围没有事件" description="扩大日期范围，或降低重要性筛选条件。"/> : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.65fr)_390px]">
          <section className="card overflow-hidden">
            <div className="card-header"><div><h2 className="section-title">日程列表</h2><p className="mt-1 text-xs text-slate-500">点击事件查看预期快照、实际值与市场反应</p></div></div>
            <div className="max-h-[calc(100vh-235px)] overflow-y-auto">
              {[...grouped.entries()].map(([day, items]) => (
                <div key={day}>
                  <div className="sticky top-0 z-10 flex items-center gap-2 border-y border-slate-200 bg-slate-50 px-5 py-2 text-sm font-bold"><CalendarClock size={16} className="text-blue-700"/>{new Date(`${day}T12:00:00`).toLocaleDateString("zh-CN", { weekday: "long", month: "long", day: "numeric" })}<span className="badge">{items.length}</span></div>
                  <div className="divide-y divide-slate-100">
                    {items.map((event) => {
                      const metric = event.metrics[0];
                      return <button key={event.id} onClick={() => setSelectedId(event.id)} className={`grid w-full gap-2 px-5 py-4 text-left transition hover:bg-slate-50 md:grid-cols-[85px_minmax(220px,1fr)_80px_95px_95px_90px] ${selectedId === event.id ? "bg-blue-50/80 ring-inset ring-1 ring-blue-200" : ""}`}>
                        <span className="font-mono text-sm font-bold text-slate-700">{format(new Date(event.scheduled_at), "HH:mm")}</span>
                        <span><span className="block font-semibold">{event.title_zh}</span><span className="mt-1 block text-xs text-slate-500">{event.reference_period ?? "—"} · {event.provider_name}</span></span>
                        <span className="text-sm">{event.country_code}</span>
                        <span className="text-sm"><span className="block text-xs text-slate-400">前值</span>{fmt(metric?.revised_previous_value ?? metric?.previous_value, metric?.unit_label)}</span>
                        <span className="text-sm"><span className="block text-xs text-slate-400">预期</span>{fmt(event.consensus_value, metric?.unit_label)}</span>
                        <span className="text-right text-xs text-red-500">{"★".repeat(event.importance_score ?? 1)}<span className="mt-1 block text-slate-500">{event.status}</span></span>
                      </button>;
                    })}
                  </div>
                </div>
              ))}
            </div>
          </section>

          <aside className="space-y-5">
            {detailQuery.isLoading ? <LoadingBlock/> : detailQuery.data ? <>
              <div className="card">
                <div className="card-header"><div><span className="badge badge-red">{"★".repeat(detailQuery.data.importance_score ?? 1)} 重要事件</span><h2 className="mt-3 text-lg font-bold leading-7">{detailQuery.data.title_zh}</h2></div>{detailQuery.data.official_url && <a className="btn btn-ghost !px-2" href={detailQuery.data.official_url} target="_blank" rel="noreferrer" aria-label="打开官方来源"><ExternalLink size={17}/></a>}</div>
                <div className="card-body space-y-4 text-sm">
                  <div className="rounded-xl bg-blue-50 p-4"><div className="text-xs text-blue-600">计划发布时间</div><div className="mt-1 font-bold text-blue-950">{new Date(detailQuery.data.scheduled_at).toLocaleString("zh-CN")}</div><div className="mt-1 text-xs text-blue-600">官方时区：{detailQuery.data.source_timezone}</div></div>
                  <div className="grid grid-cols-3 gap-2 text-center">{[...detailQuery.data.metrics.slice(0,1)].flatMap((metric) => [["前值", metric.revised_previous_value ?? metric.previous_value],["预期",detailQuery.data.consensus_value],["公布",metric.actual_value]] as const).map(([label,value])=><div key={label} className="rounded-lg border border-slate-200 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 text-lg font-bold">{fmt(value, detailQuery.data.metrics[0]?.unit_label)}</div></div>)}</div>
                  <div className="space-y-2">{detailQuery.data.metrics.map((metric)=><div key={`${metric.series_id}-${metric.transform}`} className="flex items-center justify-between border-t border-slate-100 pt-3"><span>{metric.name_zh}<span className="ml-2 text-xs text-slate-400">{metric.transform}</span></span><span className="font-semibold">{fmt(metric.actual_value, metric.unit_label)}</span></div>)}</div>
                  {alertMutation.isError && <p className="text-xs text-red-600">{(alertMutation.error as Error).message}</p>}
                </div>
              </div>
              <div className="card"><div className="card-header"><h2 className="section-title">一致预期演变</h2><Sparkles size={17} className="text-blue-600"/></div><div className="card-body">{forecastValues.length ? <BarChart labels={forecastLabels} values={forecastValues} height={220}/> : <p className="py-10 text-center text-sm text-slate-500">尚未接入商业预期快照。</p>}</div></div>
              <div className="card"><div className="card-header"><h2 className="section-title">市场反应</h2></div><div className="card-body">{detailQuery.data.market_reactions.length ? <div className="space-y-3">{detailQuery.data.market_reactions.map((reaction)=><div key={`${reaction.instrument_code}-${reaction.window_code}`} className="flex items-center justify-between text-sm"><span>{reaction.instrument_code}<span className="ml-2 text-xs text-slate-400">{reaction.window_code}</span></span><span className={Number(reaction.absolute_change ?? 0) >= 0 ? "negative" : "positive"}>{fmt(reaction.absolute_change)}</span></div>)}</div> : <p className="text-sm text-slate-500">尚无已授权的市场行情反应数据。</p>}</div></div>
            </> : <EmptyState title="选择一个事件" description="从左侧日程中选择事件查看详情。"/>}
          </aside>
        </div>
      )}
    </div>
  );
}

export default function CalendarPage() { return <Suspense fallback={<LoadingBlock/>}><CalendarContent/></Suspense>; }
