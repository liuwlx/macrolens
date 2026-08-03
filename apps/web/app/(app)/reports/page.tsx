"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Download, FileBarChart, FileText, Plus, Save, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { AICitation, AIRun, Report } from "@/lib/types";

export default function ReportsPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [sourceRunId, setSourceRunId] = useState("");
  const [createMode, setCreateMode] = useState(false);

  const reports = useQuery({ queryKey: ["reports"], queryFn: () => apiFetch<Report[]>("/me/reports") });
  const runs = useQuery({ queryKey: ["ai-runs", "reports"], queryFn: () => apiFetch<AIRun[]>("/ai/runs?limit=200") });
  const completedRuns = useMemo(() => runs.data?.filter((item) => item.status === "completed" && item.result_markdown) ?? [], [runs.data]);
  const selected = reports.data?.find((item) => item.id === selectedId) ?? reports.data?.[0];
  const citations = useQuery({
    queryKey: ["ai-citations", "report", selected?.ai_run_id],
    queryFn: () => apiFetch<AICitation[]>(`/ai/runs/${selected!.ai_run_id}/citations`),
    enabled: Boolean(selected?.ai_run_id),
  });

  useEffect(() => {
    if (!createMode && !selectedId && reports.data?.[0]) setSelectedId(reports.data[0].id);
  }, [reports.data, selectedId, createMode]);
  useEffect(() => {
    if (selected) { setTitle(selected.title); setBody(selected.content_markdown); }
  }, [selected?.id]);

  const createReport = useMutation({
    mutationFn: () => {
      const run = completedRuns.find((item) => item.id === sourceRunId);
      return apiFetch<Report>("/me/reports", {
        method: "POST",
        body: JSON.stringify({
          title: title || run?.prompt.slice(0, 120) || "MacroLens研究报告",
          content_markdown: body || null,
          ai_run_id: sourceRunId || null,
          status: "draft",
        }),
      });
    },
    onSuccess: (report) => {
      setCreateMode(false); setSelectedId(report.id); setSourceRunId(""); setTitle(""); setBody("");
      void queryClient.invalidateQueries({ queryKey: ["reports"] });
    },
  });
  const saveReport = useMutation({
    mutationFn: (status?: string) => apiFetch<Report>(`/me/reports/${selected!.id}`, {
      method: "PATCH",
      body: JSON.stringify({ title, content_markdown: body, status: status ?? selected!.status }),
    }),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["reports"] }),
  });
  const deleteReport = useMutation({
    mutationFn: () => apiFetch(`/me/reports/${selected!.id}`, { method: "DELETE" }),
    onSuccess: () => { setSelectedId(""); void queryClient.invalidateQueries({ queryKey: ["reports"] }); },
  });

  function download(format: "md" | "html") {
    if (!selected) return;
    const source = (citations.data ?? []).map((item) => `[${item.citation_no}] ${item.quote_text ?? JSON.stringify(item.locator)}`).join("\n");
    const markdown = `# ${title}\n\n${body}\n\n## 来源引用\n\n${source}`;
    const escapeHtml = (value: string) => value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
    const escaped = escapeHtml(markdown);
    const html = `<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${escapeHtml(title)}</title><style>body{font-family:system-ui;margin:48px auto;max-width:900px;line-height:1.8;color:#172033}pre{white-space:pre-wrap}</style></head><body><pre>${escaped}</pre></body></html>`;
    const blob = new Blob([format === "md" ? markdown : html], { type: format === "md" ? "text/markdown;charset=utf-8" : "text/html;charset=utf-8" });
    const link = document.createElement("a"); link.href = URL.createObjectURL(blob); link.download = `macrolens-report-${selected.id}.${format}`; link.click(); URL.revokeObjectURL(link.href);
  }

  if (reports.isLoading || runs.isLoading) return <LoadingBlock />;
  if (reports.isError) return <ErrorState message={(reports.error as Error).message} retry={() => void reports.refetch()} />;

  return <div>
    <PageHeader title="报告中心 / 研究成果交付" description="将AI分析固化为可编辑、可版本化、可发布和可审计的研究报告。" actions={<><button className="btn" onClick={()=>{setCreateMode(true);setSelectedId("");setSourceRunId("");setTitle("");setBody("");}}><Plus size={16}/>新建报告</button>{selected&&!createMode&&<><button className="btn" onClick={() => download("md")}><Download size={16}/>Markdown</button><button className="btn" onClick={() => download("html")}><Download size={16}/>HTML</button><button className="btn btn-primary" disabled={saveReport.isPending} onClick={() => saveReport.mutate("published")}><Save size={16}/>保存并发布</button></>}</>}/>

    <section className="card mb-5"><div className="card-body"><div className="grid gap-3 lg:grid-cols-[1fr_1fr_auto]"><select className="select" value={sourceRunId} onChange={(event) => { const id=event.target.value; setSourceRunId(id); const run=completedRuns.find((item)=>item.id===id); if(run){setTitle(run.prompt.slice(0,120));setBody(run.result_markdown??"");} }}><option value="">从已完成AI分析创建，或手工填写</option>{completedRuns.map((run)=><option key={run.id} value={run.id}>{run.prompt}</option>)}</select><input className="input" value={createMode ? title : ""} onChange={(event)=>setTitle(event.target.value)} disabled={!createMode} placeholder="新报告标题"/><button className="btn btn-primary" disabled={!createMode||(!sourceRunId&&!body.trim())||createReport.isPending} onClick={()=>createReport.mutate()}><Plus size={16}/>创建报告</button></div>{createMode&&<textarea className="textarea mt-3 min-h-36" value={body} onChange={(event)=>setBody(event.target.value)} placeholder="也可以直接输入报告正文。"/>}</div></section>

    {!reports.data?.length ? <EmptyState title="暂无持久化报告" description="选择一条已完成AI分析，或手工输入内容创建第一份报告。"/> : <div className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)_330px]">
      <aside className="card max-h-[calc(100vh-250px)] overflow-hidden"><div className="card-header"><div><h2 className="section-title">报告库</h2><p className="mt-1 text-xs text-slate-500">{reports.data.length} 份</p></div></div><div className="max-h-[calc(100vh-330px)] overflow-y-auto p-2">{reports.data.map((report)=><button key={report.id} onClick={()=>setSelectedId(report.id)} className={`mb-2 w-full rounded-xl p-4 text-left ${selected?.id===report.id?"bg-blue-50 ring-1 ring-blue-200":"hover:bg-slate-50"}`}><div className="flex gap-3"><FileBarChart size={18} className="mt-0.5 shrink-0 text-blue-700"/><div className="min-w-0"><div className="line-clamp-2 text-sm font-bold leading-6">{report.title}</div><div className="mt-2 flex items-center gap-2 text-xs text-slate-400"><span>v{report.version_no}</span><span className={`badge ${report.status==="published"?"badge-green":""}`}>{report.status}</span></div></div></div></button>)}</div></aside>
      <main className="card min-w-0"><div className="card-header"><div><h2 className="section-title">报告编辑器</h2><p className="mt-1 text-xs text-slate-500">正文变化会增加版本号</p></div><div className="flex gap-2"><button className="btn" disabled={saveReport.isPending} onClick={()=>saveReport.mutate(undefined)}><Save size={15}/>保存草稿</button><button className="btn btn-danger" onClick={()=>{if(confirm("确认删除该报告？"))deleteReport.mutate()}}><Trash2 size={15}/></button></div></div><div className="card-body"><input className="input mb-3 text-lg font-bold" value={title} onChange={(event)=>setTitle(event.target.value)}/><textarea className="textarea min-h-[610px] font-mono text-sm leading-7" value={body} onChange={(event)=>setBody(event.target.value)}/></div></main>
      <aside className="space-y-5"><div className="card"><div className="card-header"><h2 className="section-title">报告元数据</h2></div><div className="card-body space-y-3 text-sm">{selected&&[["状态",selected.status],["版本",selected.version_no],["创建时间",new Date(selected.created_at).toLocaleString("zh-CN")],["更新时间",new Date(selected.updated_at).toLocaleString("zh-CN")],["AI来源",selected.ai_run_id??"手工创建"]].map(([label,value])=><div key={String(label)} className="flex justify-between gap-3 border-b border-slate-100 pb-3"><span className="text-slate-500">{label}</span><span className="max-w-48 break-all text-right font-medium">{value}</span></div>)}</div><div className="p-4"><button className="btn w-full" disabled={!selected||selected.status==="archived"} onClick={()=>saveReport.mutate("archived")}><Archive size={15}/>归档报告</button></div></div><div className="card"><div className="card-header"><div><h2 className="section-title">来源引用</h2><p className="mt-1 text-xs text-slate-500">{citations.data?.length??0} 条</p></div><FileText size={17} className="text-blue-700"/></div><div className="max-h-[420px] divide-y divide-slate-100 overflow-y-auto">{citations.data?.length?citations.data.map((item)=><div key={item.id} className="p-4 text-sm"><div className="font-bold text-blue-700">[{item.citation_no}]</div><p className="mt-1 line-clamp-5 leading-6 text-slate-600">{item.quote_text??JSON.stringify(item.locator)}</p></div>):<p className="p-8 text-center text-sm text-slate-500">无AI引用；正式交付前请人工核对来源。</p>}</div></div></aside>
    </div>}
  </div>;
}
