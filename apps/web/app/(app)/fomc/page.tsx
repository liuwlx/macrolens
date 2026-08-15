"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { BellPlus, CalendarDays, ExternalLink, Landmark, Vote } from "lucide-react";
import { Suspense, useEffect, useMemo, useState } from "react";

import { BarChart } from "@/components/chart";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock, StatCard } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { FomcMeeting, FomcMeetingDetail, FomcProbability } from "@/lib/types";

const rate = (value: unknown) => value == null ? "—" : `${Number(value).toFixed(3)}%`;

function FomcContent() {
  const searchParams = useSearchParams();
  const [selectedIdOverride, setSelectedId] = useState(searchParams.get("meeting") ?? "");
  const meetingsQuery = useQuery({ queryKey: ["fomc-meetings"], queryFn: () => apiFetch<{ items: FomcMeeting[] }>("/fomc/meetings?limit=80") });
  useEffect(() => {
    const meetingId = searchParams.get("meeting");
    if (meetingId && meetingId !== selectedIdOverride) {
      // URL navigation is an external input that must replace the current selection.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSelectedId(meetingId);
    }
  }, [searchParams, selectedIdOverride]);
  const selectedId = selectedIdOverride || meetingsQuery.data?.items[0]?.id || "";
  const detailQuery = useQuery({ queryKey: ["fomc-meeting", selectedId], queryFn: () => apiFetch<FomcMeetingDetail>(`/fomc/meetings/${selectedId}`), enabled: Boolean(selectedId) });
  const probabilitiesQuery = useQuery({ queryKey: ["fomc-probabilities", selectedId], queryFn: () => apiFetch<FomcProbability[]>(`/fomc/meetings/${selectedId}/probabilities`), enabled: Boolean(selectedId) });
  const reminder = useMutation({ mutationFn: () => apiFetch("/me/alerts", { method: "POST", body: JSON.stringify({ name: "FOMC会议更新", alert_type: "fomc_update", target_type: "fomc_meeting", target_id: selectedId, rule: { document_types: ["statement", "minutes", "sep"] }, channels: ["in_app", "email"] }) }) });

  const meetings = useMemo(() => meetingsQuery.data?.items ?? [], [meetingsQuery.data]);
  const selected = detailQuery.data;
  const nextMeeting = useMemo(() => meetings.filter((item) => new Date(`${item.meeting_end}T23:59:59`) >= new Date()).sort((a,b)=>a.meeting_start.localeCompare(b.meeting_start))[0], [meetings]);
  const latestMeeting = meetings.find((item)=>item.target_rate_upper != null);
  const dotLabels = selected?.dots.map((item)=>`${item.horizon} · ${Number(item.dot_value).toFixed(2)}`) ?? [];
  const dotValues = selected?.dots.map((item)=>item.dot_count) ?? [];
  const projectionsByVariable = useMemo(() => {
    const map = new Map<string, FomcMeetingDetail["projections"]>();
    for (const row of selected?.projections ?? []) map.set(row.variable_code, [...(map.get(row.variable_code) ?? []), row]);
    return map;
  }, [selected]);

  return (
    <div>
      <PageHeader title="FOMC中心 / 会议追踪与政策观察" description="集中查看政策决定、会议文件、SEP经济预测和点阵图。" actions={<button className="btn btn-primary" disabled={!selectedId || reminder.isPending} onClick={()=>reminder.mutate()}><BellPlus size={16}/>{reminder.isSuccess ? "已订阅" : "订阅会议更新"}</button>}/>
      {meetingsQuery.isLoading ? <LoadingBlock/> : meetingsQuery.isError ? <ErrorState message={(meetingsQuery.error as Error).message} retry={()=>void meetingsQuery.refetch()}/> : !meetings.length ? <EmptyState title="FOMC数据尚未同步" description="请由管理员触发美联储会议日历与文档同步任务。"/> : <>
        <section className="grid-auto mb-5">
          <StatCard label="当前目标区间" value={latestMeeting ? `${rate(latestMeeting.target_rate_lower)} – ${rate(latestMeeting.target_rate_upper)}` : "—"} subtext={latestMeeting?.meeting_end ?? "等待同步"} trend={null} icon={<Landmark size={18}/>}/>
          <StatCard label="下次会议" value={nextMeeting?.meeting_end ?? "—"} subtext={nextMeeting ? `${nextMeeting.meeting_start} 至 ${nextMeeting.meeting_end}` : "暂无已排期会议"} trend={null} icon={<CalendarDays size={18}/>}/>
          <StatCard label="已同步会议" value={meetings.length} subtext="含历史和未来会议" trend={null} icon={<Vote size={18}/>}/>
          <StatCard label="当前声明基调" value={latestMeeting?.statement_tone ?? "—"} subtext="内部研究标签，不替代官方声明" trend={null}/>
        </section>
        <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_360px]">
          <section className="card max-h-[calc(100vh-215px)] overflow-hidden"><div className="card-header"><div><h2 className="section-title">会议时间线</h2><p className="mt-1 text-xs text-slate-500">{meetings.length} 次会议</p></div></div><div className="max-h-[calc(100vh-295px)] overflow-y-auto p-3">{meetings.map((item)=><button key={item.id} onClick={()=>setSelectedId(item.id)} className={`mb-2 w-full rounded-xl border p-4 text-left transition ${selectedId===item.id?"border-blue-300 bg-blue-50":"border-slate-200 hover:bg-slate-50"}`}><div className="flex items-start justify-between gap-2"><div className="font-bold">{item.meeting_end}</div><span className={`badge ${item.status==="completed"?"badge-green":"badge-blue"}`}>{item.status}</span></div><div className="mt-2 text-sm text-slate-600">{item.target_rate_lower == null ? "利率决定待公布" : `${rate(item.target_rate_lower)} – ${rate(item.target_rate_upper)}`}</div><div className="mt-2 text-xs text-slate-400">{item.decision_code ?? "scheduled"} · {item.statement_tone ?? "—"}</div></button>)}</div></section>
          <main className="min-w-0 space-y-5">{detailQuery.isLoading ? <LoadingBlock/> : selected ? <>
            <div className="card"><div className="card-header"><div><span className={`badge ${selected.status==="completed"?"badge-green":"badge-blue"}`}>{selected.status}</span><h2 className="mt-2 text-xl font-bold">{selected.meeting_start} — {selected.meeting_end}</h2></div>{selected.official_url && <a className="btn" href={selected.official_url} target="_blank" rel="noreferrer"><ExternalLink size={16}/>官方页面</a>}</div><div className="card-body"><div className="grid gap-3 sm:grid-cols-3">{[["政策决定",selected.decision_code ?? "待公布"],["目标区间",selected.target_rate_lower == null?"—":`${rate(selected.target_rate_lower)} – ${rate(selected.target_rate_upper)}`],["声明基调",selected.statement_tone ?? "—"]].map(([label,value])=><div key={label} className="rounded-xl border border-slate-200 p-4"><div className="text-xs text-slate-500">{label}</div><div className="mt-2 font-bold">{value}</div></div>)}</div><div className="prose-macro mt-5"><h3>会议摘要</h3><p>{selected.summary_zh ?? "官方材料已建立结构，等待会议同步或研究员审核摘要。"}</p><p className="text-sm text-slate-500">新闻发布会基调：{selected.press_conference_tone ?? "—"}</p></div></div></div>
            <div className="card"><div className="card-header"><h2 className="section-title">SEP 经济预测摘要</h2></div><div className="table-wrap"><table className="data-table"><thead><tr><th>变量</th><th>时期</th><th>统计值</th><th>预测</th><th>单位</th></tr></thead><tbody>{selected.projections.length ? selected.projections.map((item,index)=><tr key={`${item.variable_code}-${item.horizon}-${item.statistic}-${index}`}><td className="font-semibold">{item.variable_code}</td><td>{item.horizon}</td><td>{item.statistic}</td><td>{item.value == null?"—":Number(item.value).toLocaleString(undefined,{maximumFractionDigits:3})}</td><td>{item.unit}</td></tr>) : <tr><td colSpan={5} className="py-10 text-center text-slate-500">该会议未发布SEP，或尚未同步。</td></tr>}</tbody></table></div></div>
            <div className="card"><div className="card-header"><h2 className="section-title">预测变量覆盖</h2></div><div className="card-body grid-auto">{[...projectionsByVariable.entries()].map(([code,rows])=><div key={code} className="rounded-xl bg-slate-50 p-4"><div className="font-bold">{code}</div><div className="mt-1 text-xs text-slate-500">{rows.length} 个期限/统计值</div></div>)}</div></div>
          </> : null}</main>
          <aside className="space-y-5">{selected ? <>
            <div className="card"><div className="card-header"><h2 className="section-title">点阵图分布</h2></div><div className="card-body">{dotValues.length ? <BarChart labels={dotLabels} values={dotValues} height={300}/> : <p className="py-16 text-center text-sm text-slate-500">该会议没有点阵图数据。</p>}</div></div>
            <div className="card"><div className="card-header"><div><h2 className="section-title">市场隐含利率概率</h2><p className="mt-1 text-xs text-slate-500">仅在已配置商业授权数据源时展示</p></div></div><div className="card-body">{probabilitiesQuery.data?.length ? <BarChart labels={probabilitiesQuery.data.map((item)=>`${Number(item.target_lower).toFixed(2)}–${Number(item.target_upper).toFixed(2)}`)} values={probabilitiesQuery.data.map((item)=>Number(item.probability)*100)} height={260}/> : <p className="py-12 text-center text-sm text-slate-500">未配置具备展示权的 FedWatch 数据源。</p>}</div></div>
            <div className="card"><div className="card-header"><h2 className="section-title">会议文档</h2></div><div className="divide-y divide-slate-100">{selected.documents.length ? selected.documents.map((document)=><a key={document.id} className="flex items-center justify-between gap-3 p-4 text-sm hover:bg-slate-50" href={document.source_url} target="_blank" rel="noreferrer"><span><span className="block font-semibold">{document.title_zh ?? document.title}</span><span className="mt-1 block text-xs text-slate-500">{document.document_type} · {document.published_at ? new Date(document.published_at).toLocaleDateString("zh-CN") : "—"}</span></span><ExternalLink size={15}/></a>) : <p className="p-6 text-sm text-slate-500">尚未同步声明、纪要、SEP或发布会资料。</p>}</div></div>
          </> : null}</aside>
        </div>
      </>}
    </div>
  );
}

export default function FomcPage() {
  return <Suspense fallback={<LoadingBlock />}><FomcContent /></Suspense>;
}
