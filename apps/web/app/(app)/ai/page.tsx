"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, FileText, LoaderCircle, Plus, Send, Sparkles, Trash2, X } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { useAuth } from "@/components/auth-provider";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { AICapabilitiesResponse, AICitation, AIRun, DocumentSummary, Note, SavedView, SeriesSummary } from "@/lib/types";

type ContextItem = { context_type: "series" | "document" | "release_event" | "fomc_meeting" | "saved_view" | "note"; context_id: string; label: string };

function AiContent() {
  const searchParams = useSearchParams();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const userIdentity = user?.id ?? "anonymous";
  const aiRunsKey = ["ai-runs", userIdentity] as const;
  const attachedSeriesId = searchParams.get("series") ?? "";
  const attachedDataAsOf = searchParams.get("data_as_of") ?? "";
  const [prompt, setPrompt] = useState(attachedSeriesId ? "" : "请结合最新通胀、就业和FOMC材料，分析未来两次会议的政策路径，并区分事实、推断与风险情景。");
  const [mode, setMode] = useState<"quick"|"deep_research"|"scenario">("deep_research");
  const [contexts, setContexts] = useState<ContextItem[]>(() => {
    const initial: ContextItem[] = [];
    const seriesId = searchParams.get("series");
    const documentId = searchParams.get("document");
    if (seriesId) initial.push({ context_type: "series", context_id: seriesId, label: "已选指标" });
    if (documentId) initial.push({ context_type: "document", context_id: documentId, label: "已选文档" });
    return initial;
  });
  const [selectedRunId, setSelectedRunId] = useState(searchParams.get("run") ?? "");
  const [contextOpen, setContextOpen] = useState(false);
  const [contextSearch, setContextSearch] = useState("");

  const runsQuery = useQuery({ queryKey: aiRunsKey, queryFn: () => apiFetch<AIRun[]>("/ai/runs?limit=50"), refetchInterval: (query) => query.state.data?.some((item)=>["queued","running"].includes(item.status)) ? 2500 : false });
  const effectiveRunId = searchParams.get("run") ?? (selectedRunId || runsQuery.data?.[0]?.id || "");
  const selectedRun = runsQuery.data?.find((item)=>item.id===effectiveRunId);
  const citationsQuery = useQuery({ queryKey:["ai-citations",userIdentity,effectiveRunId], queryFn:()=>apiFetch<AICitation[]>(`/ai/runs/${effectiveRunId}/citations`), enabled:Boolean(effectiveRunId)&&selectedRun?.status==="completed" });
  const seriesQuery = useQuery({ queryKey:["series","ai-context",contextSearch],queryFn:()=>apiFetch<{items:SeriesSummary[]}>(`/series?q=${encodeURIComponent(contextSearch)}&limit=30`),enabled:contextOpen });
  const documentsQuery = useQuery({ queryKey:["documents","ai-context",contextSearch],queryFn:()=>apiFetch<{items:DocumentSummary[]}>(`/documents?q=${encodeURIComponent(contextSearch)}&limit=20`),enabled:contextOpen });
  const savedViewsQuery = useQuery({ queryKey:["saved-views","ai-context",userIdentity],queryFn:()=>apiFetch<SavedView[]>("/me/saved-views"),enabled:contextOpen });
  const notesQuery = useQuery({ queryKey:["notes","ai-context",userIdentity],queryFn:()=>apiFetch<Note[]>("/me/notes?limit=100"),enabled:contextOpen });
  const attachedSeriesQuery = useQuery({ queryKey:["series-detail","ai-attached",user?.id,attachedSeriesId],queryFn:({signal})=>apiFetch<SeriesSummary>(`/series/${attachedSeriesId}`,{signal}),enabled:Boolean(attachedSeriesId),staleTime:5*60_000,retry:false });
  const attachedCapabilityQuery = useQuery({ queryKey:["ai-capability","attached",user?.id,attachedSeriesId,attachedDataAsOf],queryFn:({signal})=>apiFetch<AICapabilitiesResponse>(`/ai/capabilities?series_id=${encodeURIComponent(attachedSeriesId)}${attachedDataAsOf?`&data_as_of=${encodeURIComponent(attachedDataAsOf)}`:""}`,{signal}),enabled:Boolean(attachedSeriesId),staleTime:5*60_000,retry:false });

  const createRun = useMutation({
    mutationFn:()=>apiFetch<AIRun>("/ai/runs",{method:"POST",headers:{"Idempotency-Key":crypto.randomUUID()},body:JSON.stringify({prompt,mode,data_as_of:attachedDataAsOf||null,contexts:contexts.map(({context_type,context_id})=>({context_type,context_id}))})}),
    onSuccess:(run)=>{setSelectedRunId(run.id);void queryClient.invalidateQueries({queryKey:aiRunsKey});},
  });
  const cancelRun = useMutation({ mutationFn:(id:string)=>apiFetch(`/ai/runs/${id}`,{method:"DELETE"}),onSuccess:()=>void queryClient.invalidateQueries({queryKey:aiRunsKey}) });

  const contextCandidates = useMemo(()=>[
    ...(seriesQuery.data?.items??[]).map((item)=>({context_type:"series" as const,context_id:item.id,label:item.name_zh,sub:item.canonical_code})),
    ...(documentsQuery.data?.items??[]).map((item)=>({context_type:"document" as const,context_id:item.id,label:item.title_zh??item.title,sub:item.provider_code})),
    ...(savedViewsQuery.data??[]).filter((item)=>!contextSearch||item.name.toLowerCase().includes(contextSearch.toLowerCase())).map((item)=>({context_type:"saved_view" as const,context_id:item.id,label:item.name,sub:`保存视图 · ${item.view_type}`})),
    ...(notesQuery.data??[]).filter((item)=>!contextSearch||(item.title??item.body_markdown).toLowerCase().includes(contextSearch.toLowerCase())).map((item)=>({context_type:"note" as const,context_id:item.id,label:item.title??"未命名研究笔记",sub:`研究笔记 · v${item.version_no}`})),
  ],[seriesQuery.data,documentsQuery.data,savedViewsQuery.data,notesQuery.data,contextSearch]);

  const displayedContexts=contexts.map((item)=>item.context_type==="series"&&item.context_id===attachedSeriesId&&attachedSeriesQuery.data?{...item,label:attachedSeriesQuery.data.name_zh}:item);
  function addContext(item: ContextItem) { setContexts((prev)=>prev.some((x)=>x.context_type===item.context_type&&x.context_id===item.context_id)?prev:[...prev,item]); }
  function exportRun() {
    if (!selectedRun?.result_markdown) return;
    const sourceLines=(citationsQuery.data??[]).map((item)=>`[${item.citation_no}] ${item.quote_text??JSON.stringify(item.locator)}`).join("\n");
    const blob=new Blob([`# MacroLens AI研究报告\n\n${selectedRun.result_markdown}\n\n## 引用\n${sourceLines}`],{type:"text/markdown;charset=utf-8"});
    const link=document.createElement("a");link.href=URL.createObjectURL(blob);link.download=`macrolens-report-${selectedRun.id}.md`;link.click();URL.revokeObjectURL(link.href);
  }

  return <div>
    <PageHeader title="AI分析 / 宏观研究助理" description="通过受控数据工具和官方文档RAG生成可追溯、可复核的宏观分析。" actions={<button className="btn" onClick={()=>{setSelectedRunId("");setPrompt("");setContexts([]);}}><Plus size={16}/>新建分析</button>}/>
    <section className="card mb-5"><div className="card-body">
      <div className="flex items-start gap-4"><div className="grid size-11 shrink-0 place-items-center rounded-xl bg-blue-700 text-white"><Sparkles size={20}/></div><div className="min-w-0 flex-1"><textarea className="textarea min-h-28 text-[15px] leading-7" value={prompt} onChange={(event)=>setPrompt(event.target.value)} placeholder="请提出一个明确的宏观研究问题，并指定时间范围、政策假设或需要比较的指标。"/><div className="mt-3 flex flex-wrap items-center gap-2"><select className="select !w-auto" value={mode} onChange={(event)=>setMode(event.target.value as typeof mode)}><option value="quick">快速分析</option><option value="deep_research">深度研究</option><option value="scenario">情景分析</option></select><button className="btn" onClick={()=>setContextOpen(!contextOpen)}><Plus size={16}/>选择上下文</button><button className="btn btn-primary ml-auto" disabled={prompt.trim().length<5||contexts.length===0||createRun.isPending||(Boolean(attachedSeriesId)&&attachedCapabilityQuery.data?.allowed!==true)} onClick={()=>createRun.mutate()}>{createRun.isPending?<LoaderCircle className="animate-spin" size={16}/>:<Send size={16}/>}开始分析</button></div></div></div>
      {!contexts.length&&<p className="mt-3 text-xs text-amber-700">至少选择一个指标、官方文档、发布事件、FOMC会议、保存视图或研究笔记，确保分析可以引用证据。</p>}
      {!!contexts.length&&<div className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">{displayedContexts.map((item)=><span key={`${item.context_type}-${item.context_id}`} className="badge badge-blue">{{series:"指标",document:"文档",release_event:"事件",fomc_meeting:"FOMC",saved_view:"保存视图",note:"研究笔记"}[item.context_type]} · {item.label}<button aria-label="移除上下文" onClick={()=>setContexts((prev)=>prev.filter((x)=>!(x.context_type===item.context_type&&x.context_id===item.context_id)))}><X size={13}/></button></span>)}</div>}
      {attachedSeriesId&&attachedCapabilityQuery.data&&!attachedCapabilityQuery.data.allowed&&<p className="mt-3 text-xs text-amber-700">{attachedCapabilityQuery.data.reason??"当前指标许可或模型配置不允许加入 AI 上下文。"}</p>}
      {contextOpen&&<div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4"><input className="input mb-3" value={contextSearch} onChange={(event)=>setContextSearch(event.target.value)} placeholder="搜索指标或文档"/><div className="grid max-h-72 gap-2 overflow-y-auto md:grid-cols-2">{contextCandidates.map((item)=><button key={`${item.context_type}-${item.context_id}`} onClick={()=>addContext(item)} className="rounded-lg border border-slate-200 bg-white p-3 text-left hover:border-blue-300"><div className="truncate text-sm font-semibold">{item.label}</div><div className="mt-1 text-xs text-slate-500">{item.context_type} · {item.sub}</div></button>)}</div></div>}
      {createRun.isError&&<p className="mt-3 text-sm text-red-600">{(createRun.error as Error).message}</p>}
    </div></section>

    <div className="grid gap-5 xl:grid-cols-[260px_minmax(0,1fr)_340px]">
      <section className="card max-h-[calc(100vh-285px)] overflow-hidden"><div className="card-header"><div><h2 className="section-title">分析历史</h2><p className="mt-1 text-xs text-slate-500">{runsQuery.data?.length??0} 个任务</p></div></div><div className="max-h-[calc(100vh-365px)] overflow-y-auto p-2">{runsQuery.isLoading?<div className="space-y-2">{Array.from({length:6}).map((_,i)=><div key={i} className="skeleton h-20"/>)}</div>:runsQuery.data?.length?runsQuery.data.map((run)=><button key={run.id} onClick={()=>setSelectedRunId(run.id)} className={`mb-2 w-full rounded-lg p-3 text-left ${effectiveRunId===run.id?"bg-blue-50 ring-1 ring-blue-200":"hover:bg-slate-50"}`}><div className="line-clamp-2 text-sm font-semibold leading-5">{run.prompt}</div><div className="mt-2 flex items-center justify-between text-xs text-slate-500"><span>{new Date(run.created_at).toLocaleString("zh-CN")}</span><span className={`badge ${run.status==="completed"?"badge-green":run.status==="failed"?"badge-red":"badge-blue"}`}>{run.status}</span></div></button>):<p className="p-6 text-center text-sm text-slate-500">尚无分析记录。</p>}</div></section>
      <main className="min-w-0">{runsQuery.isError?<ErrorState message={(runsQuery.error as Error).message} retry={()=>void runsQuery.refetch()}/>:!selectedRun?<EmptyState title="开始一次宏观研究" description="提出问题、选择指标或文档上下文，然后启动分析。"/>:<div className="card"><div className="card-header"><div><div className="flex items-center gap-2"><Bot size={18} className="text-blue-700"/><h2 className="section-title">分析结果</h2><span className={`badge ${selectedRun.status==="completed"?"badge-green":selectedRun.status==="failed"?"badge-red":"badge-blue"}`}>{selectedRun.status}</span></div><p className="mt-1 text-xs text-slate-500">数据截止 {new Date(selectedRun.data_as_of).toLocaleString("zh-CN")} · {selectedRun.model_name} · 提示词 {selectedRun.prompt_version}</p></div><div className="flex gap-2">{["queued","running"].includes(selectedRun.status)&&<button className="btn btn-danger" onClick={()=>cancelRun.mutate(selectedRun.id)}><Trash2 size={15}/>取消</button>}<button className="btn" onClick={exportRun} disabled={!selectedRun.result_markdown}><FileText size={15}/>导出</button></div></div><div className="card-body min-h-[560px]">{["queued","running"].includes(selectedRun.status)?<div className="flex min-h-[480px] flex-col items-center justify-center text-center"><LoaderCircle className="mb-4 animate-spin text-blue-700" size={36}/><h3 className="font-bold">AI正在读取数据与文档</h3><p className="mt-2 max-w-md text-sm leading-6 text-slate-500">任务在独立Worker中执行，页面可以关闭；结果与引用会保存在工作区。</p></div>:selectedRun.status==="failed"?<div className="flex min-h-[400px] flex-col items-center justify-center"><p className="text-red-600">{selectedRun.error_message??"分析失败，请检查模型配置与上下文许可。"}</p></div>:<article className="prose-macro whitespace-pre-wrap text-sm leading-7">{selectedRun.result_markdown}</article>}</div></div>}</main>
      <aside className="space-y-5">
        <div className="card"><div className="card-header"><h2 className="section-title">证据与引用</h2><span className="badge">{citationsQuery.data?.length??0}</span></div><div className="max-h-[460px] divide-y divide-slate-100 overflow-y-auto">{citationsQuery.isLoading?<div className="p-5"><div className="skeleton h-40"/></div>:citationsQuery.data?.length?citationsQuery.data.map((citation)=><div key={citation.id} className="p-4 text-sm"><div className="flex items-center gap-2"><span className="grid size-6 place-items-center rounded-full bg-blue-100 text-xs font-bold text-blue-700">{citation.citation_no}</span><span className="font-semibold">{citation.series_id?"时间序列证据":"文档证据"}</span></div><p className="mt-2 line-clamp-5 leading-6 text-slate-600">{citation.quote_text??JSON.stringify(citation.locator)}</p><div className="mt-2 text-xs text-slate-400">{citation.period_start??String(citation.locator.page??citation.locator.heading??"")}</div></div>):<div className="p-8 text-center text-sm text-slate-500">分析完成后显示可复核引用。</div>}</div></div>
        <div className="card"><div className="card-header"><h2 className="section-title">研究规范</h2></div><div className="card-body space-y-3 text-sm text-slate-600">{["事实数据与推断分开表达","时间序列引用固定到vintage","文档引用定位到版本、页码和片段","不允许未授权数据进入AI上下文"].map((text)=><div key={text} className="flex gap-2"><CheckCircle2 className="mt-0.5 shrink-0 text-emerald-600" size={16}/><span>{text}</span></div>)}</div></div>
      </aside>
    </div>
  </div>;
}

export default function AIPage(){return <Suspense fallback={<LoadingBlock/>}><AiContent/></Suspense>;}
