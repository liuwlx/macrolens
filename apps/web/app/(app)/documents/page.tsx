"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Bot, Download, ExternalLink, FileText, Search, Sparkles, Star } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch, queryString } from "@/lib/api";
import type { DocumentDetail, DocumentSummary } from "@/lib/types";

const documentTypes = [
  ["", "全部文档"], ["press_release", "新闻稿"], ["minutes", "会议纪要"], ["methodology", "方法说明"], ["research", "研究报告"], ["data_table", "数据表"],
];

function DocumentsContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [query, setQuery] = useState("");
  const [documentType, setDocumentType] = useState("");
  const [provider, setProvider] = useState("");
  const [selectedId, setSelectedId] = useState(searchParams.get("document") ?? "");
  const [includeContent, setIncludeContent] = useState(false);

  const documentsQuery = useQuery({
    queryKey: ["documents", query, documentType, provider],
    queryFn: () => apiFetch<{ items: DocumentSummary[]; total: number }>(`/documents${queryString({ q: query, document_type: documentType, provider, limit: 100 })}`),
  });
  useEffect(() => {
    if (!selectedId && documentsQuery.data?.items[0]) setSelectedId(documentsQuery.data.items[0].id);
  }, [documentsQuery.data, selectedId]);
  useEffect(() => {
    const documentId = searchParams.get("document");
    if (documentId && documentId !== selectedId) {
      setSelectedId(documentId);
      setIncludeContent(false);
    }
  }, [searchParams, selectedId]);
  const detailQuery = useQuery({
    queryKey: ["document", selectedId, includeContent],
    queryFn: () => apiFetch<DocumentDetail>(`/documents/${selectedId}${includeContent ? "/content" : ""}`),
    enabled: Boolean(selectedId),
  });
  const favorite = useMutation({ mutationFn: () => apiFetch("/me/favorites", { method: "POST", body: JSON.stringify({ object_type: "document", object_id: selectedId, group_name: "研究资料" }) }) });
  const summarize = useMutation({
    mutationFn: () => apiFetch<{status:string;job_id:string}>(`/documents/${selectedId}/summary`, { method: "POST" }),
    onSuccess: () => setTimeout(() => void detailQuery.refetch(), 2000),
  });

  function addToAI() {
    if (!selectedId) return;
    router.push(`/ai?document=${selectedId}`);
  }

  function exportText() {
    const doc = detailQuery.data;
    if (!doc?.license?.download_allowed) return;
    const content = `# ${doc.title_zh ?? doc.title}\n\n来源：${doc.provider_name}\n发布日期：${doc.published_at ?? "—"}\n官方地址：${doc.source_url}\n\n${doc.extracted_text ?? doc.summary_zh ?? ""}`;
    const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `${(doc.title_zh ?? doc.title).replaceAll(/[\\/:*?"<>|]/g, "-")}.md`;
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return (
    <div>
      <PageHeader title="文档检索 / 宏观文档与研究资料" description="检索官方发布、会议材料、方法说明和数据附件，并将证据加入AI研究上下文。" actions={<><button className="btn" disabled={!selectedId || favorite.isPending} onClick={()=>favorite.mutate()}><Star size={16}/>{favorite.isSuccess?"已收藏":"收藏"}</button><button className="btn btn-primary" disabled={!selectedId||detailQuery.data?.license?.ai_context_allowed===false} title={detailQuery.data?.license?.ai_context_allowed===false?"当前文档许可不允许用于AI上下文":""} onClick={addToAI}><Bot size={16}/>加入AI上下文</button></>}/>
      <div className="card mb-5 p-4">
        <div className="grid gap-3 md:grid-cols-[minmax(280px,1fr)_180px_190px]">
          <label className="relative"><Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><input className="input !pl-10" value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="搜索核心PCE、FOMC会议纪要、GDP方法说明"/></label>
          <select className="select" value={documentType} onChange={(event)=>setDocumentType(event.target.value)}>{documentTypes.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select>
          <select className="select" value={provider} onChange={(event)=>setProvider(event.target.value)}><option value="">全部机构</option><option value="BEA_API">BEA</option><option value="BLS_API_V2">BLS</option><option value="FEDERAL_RESERVE">Federal Reserve</option><option value="CENSUS_EITS_API">Census</option><option value="US_TREASURY_XML">Treasury</option><option value="EIA_API_V2">EIA</option></select>
        </div>
      </div>
      {documentsQuery.isLoading ? <LoadingBlock/> : documentsQuery.isError ? <ErrorState message={(documentsQuery.error as Error).message} retry={()=>void documentsQuery.refetch()}/> : !documentsQuery.data?.items.length ? <EmptyState title="没有匹配文档" description="尝试更换关键词或筛选条件；管理员也可以触发文档采集任务。"/> : (
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1.15fr)_minmax(420px,.85fr)]">
          <section className="card overflow-hidden">
            <div className="card-header"><div><h2 className="section-title">检索结果</h2><p className="mt-1 text-xs text-slate-500">共 {documentsQuery.data.total} 份文档</p></div></div>
            <div className="max-h-[calc(100vh-245px)] divide-y divide-slate-100 overflow-y-auto">
              {documentsQuery.data.items.map((document)=><button key={document.id} onClick={()=>{setSelectedId(document.id);setIncludeContent(false);}} className={`w-full p-5 text-left transition hover:bg-slate-50 ${selectedId===document.id?"bg-blue-50/70 ring-inset ring-1 ring-blue-200":""}`}>
                <div className="flex items-start gap-4"><div className="grid size-11 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700"><FileText size={20}/></div><div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className="badge badge-blue">{document.document_type}</span><span className="text-xs font-semibold text-slate-500">{document.provider_code}</span><span className="text-xs text-slate-400">{document.published_at ? new Date(document.published_at).toLocaleDateString("zh-CN") : "—"}</span></div><h3 className="mt-2 font-bold leading-6">{document.title_zh ?? document.title}</h3><p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">{document.summary_zh ?? "尚未生成摘要。打开文档后可查看已提取正文与引用块。"}</p><div className="mt-3 flex flex-wrap gap-2">{document.related_series.slice(0,6).map((series)=><span key={series.id} className="badge">{series.name_zh}</span>)}</div></div></div>
              </button>)}
            </div>
          </section>
          <aside className="space-y-5">{detailQuery.isLoading ? <LoadingBlock/> : detailQuery.data ? <>
            <div className="card"><div className="card-header"><div><div className="flex flex-wrap gap-2"><span className="badge badge-blue">{detailQuery.data.document_type}</span><span className="badge">{detailQuery.data.provider_name}</span></div><h2 className="mt-3 text-xl font-bold leading-8">{detailQuery.data.title_zh ?? detailQuery.data.title}</h2></div></div><div className="card-body space-y-5">
              <div className="grid grid-cols-2 gap-3 text-sm">{[["发布日期",detailQuery.data.published_at?new Date(detailQuery.data.published_at).toLocaleString("zh-CN"):"—"],["语言",detailQuery.data.language],["版本",detailQuery.data.version_no??"—"],["版权状态",detailQuery.data.copyright_status]].map(([label,value])=><div key={String(label)} className="rounded-lg bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 font-semibold">{String(value)}</div></div>)}</div>
              {detailQuery.data.license?.attribution_text&&<p className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-xs leading-5 text-blue-800">署名：{detailQuery.data.license.attribution_text}</p>}
              <div><div className="mb-2 flex items-center gap-2 font-bold"><Sparkles size={17} className="text-blue-600"/>智能摘要</div><p className="text-sm leading-7 text-slate-600">{detailQuery.data.summary_zh ?? "该文档尚未完成AI摘要。可由管理员触发文档解析与向量化任务。"}</p></div>
              <div className="flex flex-wrap gap-2"><a className="btn btn-primary" href={detailQuery.data.source_url} target="_blank" rel="noreferrer"><ExternalLink size={16}/>打开官方文档</a><button className="btn" onClick={()=>setIncludeContent(true)}>读取正文</button><button className="btn" onClick={()=>summarize.mutate()} disabled={summarize.isPending||Boolean(detailQuery.data.summary_zh)}><Sparkles size={16}/>{summarize.isPending?"排队中":detailQuery.data.summary_zh?"已有摘要":"生成摘要"}</button><button className="btn" onClick={exportText} disabled={!detailQuery.data.extracted_text||!detailQuery.data.license?.download_allowed} title={detailQuery.data.license?.download_allowed?"导出已解析摘录":"当前文档许可不允许下载"}><Download size={16}/>导出摘录</button></div>
            </div></div>
            <div className="card"><div className="card-header"><h2 className="section-title">正文与引用块</h2><span className="text-xs text-slate-500">{detailQuery.data.chunks.length} 个片段</span></div><div className="card-body max-h-[520px] overflow-y-auto">{includeContent ? detailQuery.data.chunks.length ? <div className="space-y-4">{detailQuery.data.chunks.map((chunk)=><article key={chunk.id} className="rounded-xl border border-slate-200 p-4"><div className="mb-2 flex justify-between text-xs text-slate-400"><span>{chunk.heading_path ?? `片段 ${chunk.chunk_no}`}</span><span>{chunk.page_start ? `第 ${chunk.page_start}${chunk.page_end&&chunk.page_end!==chunk.page_start?`–${chunk.page_end}`:""} 页` : "网页正文"}</span></div><p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">{chunk.content}</p></article>)}</div> : <p className="py-12 text-center text-sm text-slate-500">文档尚未切块。请检查文档Worker任务状态。</p> : <div className="py-12 text-center"><p className="mb-4 text-sm text-slate-500">正文按需读取，避免列表页传输大型文档。</p><button className="btn" onClick={()=>setIncludeContent(true)}>加载正文与引用</button></div>}</div></div>
          </> : <EmptyState title="选择一份文档" description="从检索结果中选择文档查看详情。"/>}</aside>
        </div>
      )}
    </div>
  );
}

export default function DocumentsPage() {
  return <Suspense fallback={<LoadingBlock />}><DocumentsContent /></Suspense>;
}
