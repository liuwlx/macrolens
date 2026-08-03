"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellRing, CheckCheck, Mail, Plus, Power, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch, queryString } from "@/lib/api";
import type { AlertRule, FomcMeeting, Notification, ReleaseEvent, SeriesSummary } from "@/lib/types";

const types = [
  ["release_reminder", "数据发布提醒"],
  ["threshold", "指标阈值"],
  ["revision", "历史修订"],
  ["new_document", "新文档"],
  ["fomc_update", "FOMC更新"],
  ["digest", "定期简报"],
] as const;

function isoDate(offsetDays: number) {
  const value = new Date();
  value.setUTCDate(value.getUTCDate() + offsetDays);
  return value.toISOString().slice(0, 10);
}

export default function AlertsPage() {
  const client = useQueryClient();
  const router = useRouter();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [alertType, setAlertType] = useState<(typeof types)[number][0]>("digest");
  const [targetId, setTargetId] = useState("");
  const [email, setEmail] = useState(true);
  const [operator, setOperator] = useState(">=");
  const [threshold, setThreshold] = useState("");
  const [minutesBefore, setMinutesBefore] = useState("30");
  const [providerCode, setProviderCode] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [digestSchedule, setDigestSchedule] = useState("0 8 * * 1-5");

  const alerts = useQuery({ queryKey: ["alerts"], queryFn: () => apiFetch<AlertRule[]>("/me/alerts") });
  const notifications = useQuery({ queryKey: ["notifications"], queryFn: () => apiFetch<Notification[]>("/me/notifications") });
  const series = useQuery({
    queryKey: ["series", "alert-targets"],
    queryFn: () => apiFetch<{ items: SeriesSummary[] }>("/series?limit=200"),
    enabled: showCreate && ["threshold", "revision"].includes(alertType),
  });
  const events = useQuery({
    queryKey: ["release-events", "alert-targets"],
    queryFn: () => apiFetch<{ items: ReleaseEvent[] }>(`/release-events${queryString({ start: isoDate(-1), end: isoDate(180), country: "US", limit: 500 })}`),
    enabled: showCreate && alertType === "release_reminder",
  });
  const meetings = useQuery({
    queryKey: ["fomc-meetings", "alert-targets"],
    queryFn: () => apiFetch<{ items: FomcMeeting[] }>("/fomc/meetings?limit=80"),
    enabled: showCreate && alertType === "fomc_update",
  });

  const targetOptions = useMemo(() => {
    if (["threshold", "revision"].includes(alertType)) {
      return (series.data?.items ?? []).map((item) => ({ id: item.id, label: `${item.name_zh} · ${item.canonical_code}` }));
    }
    if (alertType === "release_reminder") {
      return (events.data?.items ?? []).map((item) => ({ id: item.id, label: `${new Date(item.scheduled_at).toLocaleString("zh-CN")} · ${item.title_zh}` }));
    }
    if (alertType === "fomc_update") {
      return (meetings.data?.items ?? []).map((item) => ({ id: item.id, label: `${item.meeting_start} — ${item.meeting_end}` }));
    }
    return [];
  }, [alertType, events.data, meetings.data, series.data]);

  const create = useMutation({
    mutationFn: () => {
      let target_type: string | null = null;
      let target_id: string | null = targetId || null;
      let rule: Record<string, unknown> = {};
      if (alertType === "release_reminder") {
        target_type = "release_event";
        rule = { minutes_before: Number(minutesBefore) };
      } else if (alertType === "threshold") {
        target_type = "series";
        rule = { operator, value: Number(threshold), cooldown_hours: 24 };
      } else if (alertType === "revision") {
        target_type = "series";
        rule = {};
      } else if (alertType === "fomc_update") {
        target_type = target_id ? "fomc_meeting" : null;
        rule = {};
      } else if (alertType === "new_document") {
        target_id = null;
        rule = { provider_code: providerCode || undefined, document_type: documentType || undefined };
      } else {
        target_id = null;
        rule = { schedule: digestSchedule };
      }
      return apiFetch<AlertRule>("/me/alerts", {
        method: "POST",
        body: JSON.stringify({ name, alert_type: alertType, target_type, target_id, rule, channels: email ? ["in_app", "email"] : ["in_app"] }),
      });
    },
    onSuccess: () => {
      setShowCreate(false);
      setName("");
      setTargetId("");
      void client.invalidateQueries({ queryKey: ["alerts"] });
    },
  });
  const toggle = useMutation({ mutationFn: ({ id, active }: { id: string; active: boolean }) => apiFetch<AlertRule>(`/me/alerts/${id}?active=${active}`, { method: "PATCH" }), onSuccess: () => void client.invalidateQueries({ queryKey: ["alerts"] }) });
  const remove = useMutation({ mutationFn: (id: string) => apiFetch(`/me/alerts/${id}`, { method: "DELETE" }), onSuccess: () => void client.invalidateQueries({ queryKey: ["alerts"] }) });
  const read = useMutation({
    mutationFn: ({ id }: { id: string; url?: string | null }) => apiFetch<Notification>(`/me/notifications/${id}/read`, { method: "POST" }),
    onSuccess: (_value, variables) => {
      void client.invalidateQueries({ queryKey: ["notifications"] });
      if (variables.url) router.push(variables.url);
    },
  });
  const unread = notifications.data?.filter((item) => !item.read_at).length ?? 0;
  const targetRequired = ["release_reminder", "threshold", "revision"].includes(alertType);
  const formValid = name.trim() && (!targetRequired || targetId) && (alertType !== "threshold" || threshold.trim());

  return <div>
    <PageHeader title="提醒中心 / 规则与通知" description="通过站内消息和邮件跟踪发布、阈值、修订、文档与FOMC更新。" actions={<button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}><Plus size={16}/>新建提醒</button>}/>
    {showCreate && <section className="card mb-5"><div className="card-body"><h2 className="section-title mb-4">创建提醒规则</h2><div className="grid gap-3 md:grid-cols-2">
      <label className="text-xs text-slate-500">名称<input className="input mt-1" value={name} onChange={(event) => setName(event.target.value)} placeholder="核心PCE发布前30分钟"/></label>
      <label className="text-xs text-slate-500">类型<select className="select mt-1" value={alertType} onChange={(event) => { setAlertType(event.target.value as typeof alertType); setTargetId(""); }}>{types.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      {targetOptions.length > 0 && <label className="text-xs text-slate-500 md:col-span-2">跟踪目标<select className="select mt-1" value={targetId} onChange={(event) => setTargetId(event.target.value)}><option value="">请选择</option>{targetOptions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label>}
      {alertType === "release_reminder" && <label className="text-xs text-slate-500">提前分钟数<input className="input mt-1" type="number" min="5" max="10080" value={minutesBefore} onChange={(event) => setMinutesBefore(event.target.value)}/></label>}
      {alertType === "threshold" && <><label className="text-xs text-slate-500">比较符<select className="select mt-1" value={operator} onChange={(event) => setOperator(event.target.value)}>{[">=", "<=", ">", "<", "=="].map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-xs text-slate-500">阈值<input className="input mt-1" type="number" step="any" value={threshold} onChange={(event) => setThreshold(event.target.value)}/></label></>}
      {alertType === "new_document" && <><label className="text-xs text-slate-500">来源机构<select className="select mt-1" value={providerCode} onChange={(event) => setProviderCode(event.target.value)}><option value="">全部机构</option>{["BEA_API", "BLS_API_V2", "FEDERAL_RESERVE", "CENSUS_EITS_API", "US_TREASURY_XML", "EIA_API_V2"].map((item) => <option key={item}>{item}</option>)}</select></label><label className="text-xs text-slate-500">文档类型<select className="select mt-1" value={documentType} onChange={(event) => setDocumentType(event.target.value)}><option value="">全部类型</option>{["press_release", "minutes", "methodology", "projection", "statement", "research"].map((item) => <option key={item}>{item}</option>)}</select></label></>}
      {alertType === "fomc_update" && <p className="text-xs leading-6 text-slate-500 md:col-span-2">不选择会议时，将提醒所有新发布的声明、纪要、SEP和新闻发布会材料。</p>}
      {alertType === "digest" && <label className="text-xs text-slate-500 md:col-span-2">Cron计划（UTC）<input className="input mt-1 font-mono" value={digestSchedule} onChange={(event) => setDigestSchedule(event.target.value)} placeholder="0 8 * * 1-5"/></label>}
    </div><div className="mt-4 flex items-center gap-3"><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={email} onChange={(event) => setEmail(event.target.checked)}/><Mail size={15}/>同时发送邮件</label><div className="ml-auto flex gap-2"><button className="btn" onClick={() => setShowCreate(false)}>取消</button><button className="btn btn-primary" disabled={!formValid || create.isPending} onClick={() => create.mutate()}>保存规则</button></div></div>{create.isError && <p className="mt-3 text-sm text-red-600">{(create.error as Error).message}</p>}</div></section>}
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_420px]">
      <section className="card"><div className="card-header"><div><h2 className="section-title">提醒规则</h2><p className="mt-1 text-xs text-slate-500">{alerts.data?.length ?? 0} 条规则</p></div></div>{alerts.isLoading ? <div className="p-5"><div className="skeleton h-72"/></div> : alerts.isError ? <div className="p-5"><ErrorState message={(alerts.error as Error).message}/></div> : alerts.data?.length ? <div className="divide-y divide-slate-100">{alerts.data.map((alert) => <div key={alert.id} className="flex items-start gap-4 p-5"><div className={`grid size-11 shrink-0 place-items-center rounded-xl ${alert.active ? "bg-blue-50 text-blue-700" : "bg-slate-100 text-slate-400"}`}><BellRing size={19}/></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><h3 className="font-bold">{alert.name}</h3><span className="badge">{types.find(([value]) => value === alert.alert_type)?.[1] ?? alert.alert_type}</span><span className={`badge ${alert.active ? "badge-green" : ""}`}>{alert.active ? "运行中" : "已暂停"}</span></div><pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs leading-5 text-slate-500">{JSON.stringify(alert.rule, null, 2)}</pre><div className="mt-2 flex gap-2 text-xs text-slate-400"><span>{alert.channels.join(" + ")}</span><span>·</span><span>上次检查 {alert.last_evaluated_at ? new Date(alert.last_evaluated_at).toLocaleString("zh-CN") : "尚未运行"}</span></div></div><div className="flex gap-2"><button className="btn !min-h-8 !px-2" title={alert.active ? "暂停" : "启用"} onClick={() => toggle.mutate({ id: alert.id, active: !alert.active })}><Power size={15}/></button><button className="btn btn-ghost btn-danger !min-h-8 !px-2" onClick={() => remove.mutate(alert.id)}><Trash2 size={15}/></button></div></div>)}</div> : <div className="p-5"><EmptyState title="没有提醒规则" description="创建发布、阈值、修订、文档或定期简报提醒。"/></div>}</section>
      <aside className="card"><div className="card-header"><div><h2 className="section-title">通知</h2><p className="mt-1 text-xs text-slate-500">{unread} 条未读</p></div><Bell size={18} className="text-blue-700"/></div>{notifications.isLoading ? <div className="p-5"><div className="skeleton h-72"/></div> : notifications.isError ? <div className="p-5"><ErrorState message={(notifications.error as Error).message}/></div> : notifications.data?.length ? <div className="max-h-[calc(100vh-300px)] divide-y divide-slate-100 overflow-y-auto">{notifications.data.map((item) => <button key={item.id} onClick={() => read.mutate({ id: item.id, url: item.action_url })} className={`w-full p-4 text-left hover:bg-slate-50 ${item.read_at ? "opacity-65" : "bg-blue-50/40"}`}><div className="flex items-start gap-3"><div className="mt-0.5">{item.read_at ? <CheckCheck size={16} className="text-slate-400"/> : <span className="block size-2 rounded-full bg-blue-600"/>}</div><div className="min-w-0"><div className="font-semibold">{item.title}</div><p className="mt-1 text-sm leading-6 text-slate-500">{item.body ?? ""}</p><div className="mt-2 text-xs text-slate-400">{new Date(item.created_at).toLocaleString("zh-CN")}</div></div></div></button>)}</div> : <p className="p-10 text-center text-sm text-slate-500">暂无通知。</p>}</aside>
    </div>
  </div>;
}
