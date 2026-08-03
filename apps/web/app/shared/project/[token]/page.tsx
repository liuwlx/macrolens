"use client";

import { useQuery } from "@tanstack/react-query";
import { FileText, FolderKanban } from "lucide-react";
import { useParams } from "next/navigation";

import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { ProjectDetail } from "@/lib/types";

export default function SharedProjectPage() {
  const params = useParams<{ token: string }>();
  const project = useQuery({
    queryKey: ["shared-project", params.token],
    queryFn: () => apiFetch<ProjectDetail>(`/shared/projects/${encodeURIComponent(params.token)}`),
  });

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-10 text-slate-900">
      <div className="mx-auto max-w-5xl">
        <header className="mb-6 flex items-center gap-3">
          <div className="grid size-11 place-items-center rounded-xl bg-blue-700 text-white"><FolderKanban size={21}/></div>
          <div><div className="text-lg font-black text-blue-800">MacroLens | 宏观镜</div><div className="text-xs text-slate-500">只读研究项目分享</div></div>
        </header>
        {project.isLoading ? <LoadingBlock /> : project.isError ? <ErrorState message={(project.error as Error).message} retry={() => void project.refetch()} /> : !project.data ? <EmptyState title="项目不可用" description="分享链接可能已过期或被撤销。" /> : <div className="space-y-5">
          <section className="card p-6"><h1 className="text-2xl font-black">{project.data.name}</h1><p className="mt-2 text-sm leading-7 text-slate-600">{project.data.description ?? "暂无项目描述"}</p><div className="mt-4 flex gap-2 text-xs text-slate-500"><span className="badge">{project.data.items.length} 项资料</span><span className="badge">{project.data.notes.length} 条笔记</span><span className="badge badge-blue">只读</span></div></section>
          <div className="grid gap-5 lg:grid-cols-[.8fr_1.2fr]">
            <section className="card"><div className="card-header"><h2 className="section-title">项目资料</h2></div><div className="divide-y divide-slate-100">{project.data.items.length ? project.data.items.map((item)=><div key={item.id} className="flex gap-3 p-4"><FileText size={18} className="mt-0.5 shrink-0 text-blue-700"/><div><div className="text-sm font-semibold">{item.title_override ?? item.object_id}</div><div className="mt-1 text-xs text-slate-400">{item.object_type}</div></div></div>) : <p className="p-8 text-center text-sm text-slate-500">暂无资料</p>}</div></section>
            <section className="card"><div className="card-header"><h2 className="section-title">研究笔记</h2></div><div className="divide-y divide-slate-100">{project.data.notes.length ? project.data.notes.map((note)=><article key={note.id} className="p-5"><h3 className="font-bold">{note.title ?? "研究笔记"}</h3><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">{note.body_markdown}</p></article>) : <p className="p-8 text-center text-sm text-slate-500">暂无笔记</p>}</div></section>
          </div>
        </div>}
      </div>
    </main>
  );
}
