"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { addDays, format } from "date-fns";
import { Activity, CalendarClock, Database, Landmark, RefreshCw, TrendingUp } from "lucide-react";
import Link from "next/link";

import { TimeSeriesChart } from "@/components/chart";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock, StatCard } from "@/components/ui";
import { apiFetch, queryString } from "@/lib/api";
import type { ObservationResponse, ReleaseEvent, SeriesSummary } from "@/lib/types";

export default function HomePage() {
  const seriesQuery = useQuery({ queryKey: ["series", "home"], queryFn: () => apiFetch<{ items: SeriesSummary[]; total: number }>("/series?limit=12") });
  const today = new Date();
  const releasesQuery = useQuery({
    queryKey: ["releases", "home", format(today, "yyyy-MM-dd")],
    queryFn: () => apiFetch<{ items: ReleaseEvent[] }>(`/release-events${queryString({ start: format(today, "yyyy-MM-dd"), end: format(addDays(today, 14), "yyyy-MM-dd"), country: "US", limit: 12 })}`),
  });
  const chartSeries = (seriesQuery.data?.items ?? []).slice(0, 3);
  const charts = useQueries({
    queries: chartSeries.map((series) => ({ queryKey: ["observations", series.id, series.default_transform, "home"], queryFn: () => apiFetch<ObservationResponse>(`/series/${series.id}/observations${queryString({ transform: series.default_transform })}`), enabled: !!series.id })),
  });

  return (
    <div>
      <PageHeader title="首页 / 宏观总览" description="一站式追踪美国宏观经济的关键指标、事件与政策信号。" actions={<button className="btn" onClick={() => { void seriesQuery.refetch(); void releasesQuery.refetch(); }}><RefreshCw size={16}/>刷新数据</button>} />
      {seriesQuery.isLoading ? <LoadingBlock /> : seriesQuery.isError ? <ErrorState message={(seriesQuery.error as Error).message} retry={() => void seriesQuery.refetch()} /> : !seriesQuery.data?.items.length ? <EmptyState title="指标目录尚未初始化" description="请先执行数据库迁移、seed，并为官方数据源配置 API Key 后触发同步。" /> : (
        <>
          <section className="grid-auto mb-5">
            {seriesQuery.data.items.slice(0, 6).map((series, index) => <StatCard key={series.id} label={series.name_zh} value={series.latest_value == null ? "—" : Number(series.latest_value).toLocaleString(undefined, { maximumFractionDigits: 3 })} subtext={series.latest_period ?? "等待同步"} trend={null} icon={[<Activity key="a" size={18}/>,<TrendingUp key="t" size={18}/>,<Database key="d" size={18}/>][index % 3]} />)}
          </section>
          <section className="mb-5 grid gap-5 xl:grid-cols-[1.6fr_.8fr]">
            <div className="card"><div className="card-header"><div><h2 className="section-title">核心指标趋势</h2><p className="mt-1 text-xs text-slate-500">默认口径来自指标目录，可在数据总览切换同比、环比和历史版本。</p></div><Link className="text-sm font-semibold text-blue-700" href="/compare">进入对比分析</Link></div><div className="card-body">{charts.some((query) => query.isLoading) ? <div className="skeleton h-[330px]"/> : <TimeSeriesChart series={charts.flatMap((query, index) => query.data ? [{ name: chartSeries[index].name_zh, data: query.data.data.slice(-120), axis: index === 2 ? 1 : 0 }] : [])}/>}</div></div>
            <div className="card"><div className="card-header"><h2 className="section-title">即将发布</h2><Link href="/calendar" className="text-sm font-semibold text-blue-700">查看日历</Link></div><div className="divide-y divide-slate-100">{releasesQuery.data?.items?.length ? releasesQuery.data.items.slice(0, 8).map((event) => <Link href={`/calendar?event=${event.id}`} key={event.id} className="flex items-start gap-3 p-4 hover:bg-slate-50"><div className="mt-1 grid size-9 shrink-0 place-items-center rounded-lg bg-blue-50 text-blue-700"><CalendarClock size={17}/></div><div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{event.title_zh}</div><div className="mt-1 text-xs text-slate-500">{new Date(event.scheduled_at).toLocaleString("zh-CN")} · {event.provider_code}</div></div><span className="text-xs text-red-500">{"★".repeat(event.importance_score ?? 1)}</span></Link>) : <div className="p-8 text-center text-sm text-slate-500">当前日期范围没有已同步的发布事件。</div>}</div></div>
          </section>
          <section className="grid gap-5 lg:grid-cols-3">
            {[{title:"数据总览",desc:"查看指标树、历史数据、修订与来源血缘。",href:"/data",icon:Database},{title:"FOMC中心",desc:"跟踪会议决定、SEP、点阵图与政策文件。",href:"/fomc",icon:Landmark},{title:"AI研究助理",desc:"基于指定指标和官方文档生成带引用的分析。",href:"/ai",icon:Activity}].map((item)=><Link key={item.href} href={item.href} className="card group p-5 transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md"><div className="mb-4 grid size-11 place-items-center rounded-xl bg-blue-50 text-blue-700"><item.icon size={21}/></div><h3 className="font-bold">{item.title}</h3><p className="mt-2 text-sm leading-6 text-slate-500">{item.desc}</p></Link>)}
          </section>
        </>
      )}
    </div>
  );
}
