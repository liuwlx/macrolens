"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Copy, Download, FileText, FolderKanban, Plus, Save, Share2, Trash2 } from "lucide-react";
import { Suspense, useEffect, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { Note, Project, ProjectDetail, ProjectShare } from "@/lib/types";

function WorkspaceContent(){
  const queryClient=useQueryClient();
  const searchParams=useSearchParams();
  const [selectedIdOverride,setSelectedId]=useState(searchParams.get("project")??"");
  const [showCreate,setShowCreate]=useState(false);
  const [name,setName]=useState("");
  const [description,setDescription]=useState("");
  const [noteTitle,setNoteTitle]=useState("");
  const [noteBody,setNoteBody]=useState("");
  const [editingNote,setEditingNote]=useState<Note|null>(null);
  const [shareUrl,setShareUrl]=useState("");

  const projectsQuery=useQuery({queryKey:["projects"],queryFn:()=>apiFetch<Project[]>("/me/projects")});
  useEffect(()=>{const projectId=searchParams.get("project");if(projectId&&projectId!==selectedIdOverride){
    // URL navigation is an external input that must replace the current selection.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setSelectedId(projectId);
  }},[searchParams,selectedIdOverride]);
  const selectedId=selectedIdOverride||projectsQuery.data?.[0]?.id||"";
  const detailQuery=useQuery({queryKey:["project",selectedId],queryFn:()=>apiFetch<ProjectDetail>(`/me/projects/${selectedId}`),enabled:Boolean(selectedId)});
  const createProject=useMutation({mutationFn:()=>apiFetch<Project>("/me/projects",{method:"POST",body:JSON.stringify({name,description:description||null})}),onSuccess:(project)=>{setSelectedId(project.id);setName("");setDescription("");setShowCreate(false);void queryClient.invalidateQueries({queryKey:["projects"]});}});
  const deleteProject=useMutation({mutationFn:(id:string)=>apiFetch(`/me/projects/${id}`,{method:"DELETE"}),onSuccess:()=>{setSelectedId("");void queryClient.invalidateQueries({queryKey:["projects"]});}});
  const saveNote=useMutation({mutationFn:()=>editingNote?apiFetch<Note>(`/me/projects/${selectedId}/notes/${editingNote.id}`,{method:"PATCH",body:JSON.stringify({title:noteTitle||null,body_markdown:noteBody})}):apiFetch<Note>(`/me/projects/${selectedId}/notes`,{method:"POST",body:JSON.stringify({title:noteTitle||null,body_markdown:noteBody})}),onSuccess:()=>{setEditingNote(null);setNoteTitle("");setNoteBody("");void queryClient.invalidateQueries({queryKey:["project",selectedId]});}});
  const deleteNote=useMutation({mutationFn:(id:string)=>apiFetch(`/me/projects/${selectedId}/notes/${id}`,{method:"DELETE"}),onSuccess:()=>void queryClient.invalidateQueries({queryKey:["project",selectedId]})});
  const deleteItem=useMutation({mutationFn:(id:string)=>apiFetch(`/me/projects/${selectedId}/items/${id}`,{method:"DELETE"}),onSuccess:()=>void queryClient.invalidateQueries({queryKey:["project",selectedId]})});
  const createShare=useMutation({mutationFn:()=>apiFetch<ProjectShare>(`/me/projects/${selectedId}/shares`,{method:"POST",body:JSON.stringify({expires_in_days:7})}),onSuccess:(share)=>setShareUrl(share.share_url??"")});

  function editNote(note:Note){setEditingNote(note);setNoteTitle(note.title??"");setNoteBody(note.body_markdown);}
  function exportProject(){const project=detailQuery.data;if(!project)return;const content=[`# ${project.name}`,project.description??"",...project.notes.map((note)=>`## ${note.title??"研究笔记"}\n\n${note.body_markdown}`),"## 项目资料",...project.items.map((item)=>`- ${item.object_type}: ${item.title_override??item.object_id}`)].join("\n\n");const blob=new Blob([content],{type:"text/markdown;charset=utf-8"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=`${project.name.replaceAll(/[\\/:*?"<>|]/g,"-")}.md`;a.click();URL.revokeObjectURL(a.href);}

  return <div>
    <PageHeader title="研究工作台 / 项目与研究沉淀" description="把指标、文档、发布事件、AI结果和研究笔记组织成可交付项目。" actions={<><button className="btn" disabled={!detailQuery.data||createShare.isPending} onClick={()=>createShare.mutate()}><Share2 size={16}/>生成分享链接</button><button className="btn" disabled={!detailQuery.data} onClick={exportProject}><Download size={16}/>导出项目</button><button className="btn btn-primary" onClick={()=>setShowCreate(true)}><Plus size={16}/>新建项目</button></>}/>
    {shareUrl&&<div className="mb-5 flex flex-col gap-3 rounded-xl border border-blue-200 bg-blue-50 p-4 md:flex-row md:items-center"><div className="min-w-0 flex-1"><div className="text-sm font-bold text-blue-900">只读分享链接已生成，7天后过期</div><div className="mt-1 truncate text-xs text-blue-700">{shareUrl}</div></div><button className="btn bg-white" onClick={async()=>{await navigator.clipboard.writeText(shareUrl);}}><Copy size={15}/>复制链接</button></div>}
    {showCreate&&<div className="card mb-5"><div className="card-body"><h2 className="section-title mb-4">新建研究项目</h2><div className="grid gap-3 md:grid-cols-[1fr_1.5fr_auto]"><input className="input" value={name} onChange={(e)=>setName(e.target.value)} placeholder="项目名称"/><input className="input" value={description} onChange={(e)=>setDescription(e.target.value)} placeholder="研究目标与范围"/><div className="flex gap-2"><button className="btn" onClick={()=>setShowCreate(false)}>取消</button><button className="btn btn-primary" disabled={!name.trim()||createProject.isPending} onClick={()=>createProject.mutate()}>创建</button></div></div></div></div>}
    {projectsQuery.isLoading?<LoadingBlock/>:projectsQuery.isError?<ErrorState message={(projectsQuery.error as Error).message} retry={()=>void projectsQuery.refetch()}/>:!projectsQuery.data?.length?<EmptyState title="还没有研究项目" description="创建项目后，可从数据、文档、发布和AI页面把资料加入工作台。" action={<button className="btn btn-primary" onClick={()=>setShowCreate(true)}><Plus size={16}/>创建第一个项目</button>}/>:<div className="grid gap-5 xl:grid-cols-[290px_minmax(0,1fr)]">
      <aside className="card max-h-[calc(100vh-210px)] overflow-hidden"><div className="card-header"><div><h2 className="section-title">我的项目</h2><p className="mt-1 text-xs text-slate-500">{projectsQuery.data.length} 个</p></div></div><div className="max-h-[calc(100vh-290px)] overflow-y-auto p-2">{projectsQuery.data.map((project)=><button key={project.id} onClick={()=>setSelectedId(project.id)} className={`mb-2 w-full rounded-xl p-4 text-left ${selectedId===project.id?"bg-blue-50 ring-1 ring-blue-200":"hover:bg-slate-50"}`}><div className="flex items-start gap-3"><FolderKanban className="mt-0.5 shrink-0 text-blue-700" size={19}/><div className="min-w-0"><div className="truncate font-bold">{project.name}</div><div className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{project.description??"暂无描述"}</div><div className="mt-2 text-[11px] text-slate-400">更新 {new Date(project.updated_at).toLocaleString("zh-CN")}</div></div></div></button>)}</div></aside>
      <main className="min-w-0 space-y-5">{detailQuery.isLoading?<LoadingBlock/>:detailQuery.isError?<ErrorState message={(detailQuery.error as Error).message} retry={()=>void detailQuery.refetch()}/>:detailQuery.data?<>
        <section className="card"><div className="card-header"><div><h2 className="text-xl font-bold">{detailQuery.data.name}</h2><p className="mt-1 text-sm text-slate-500">{detailQuery.data.description??"暂无项目描述"}</p></div><button className="btn btn-danger" onClick={()=>{if(confirm("确认删除该项目及其笔记？"))deleteProject.mutate(detailQuery.data!.id)}}><Trash2 size={16}/>删除项目</button></div><div className="card-body grid-auto">{[["项目资料",detailQuery.data.items.length],["研究笔记",detailQuery.data.notes.length],["项目状态",detailQuery.data.status],["创建时间",new Date(detailQuery.data.created_at).toLocaleDateString("zh-CN")]].map(([label,value])=><div key={label as string} className="rounded-xl bg-slate-50 p-4"><div className="text-xs text-slate-500">{label}</div><div className="mt-2 text-xl font-bold">{value}</div></div>)}</div></section>
        <section className="grid gap-5 lg:grid-cols-[1.2fr_.8fr]">
          <div className="card"><div className="card-header"><div><h2 className="section-title">研究笔记</h2><p className="mt-1 text-xs text-slate-500">支持Markdown，更新时保留版本号。</p></div></div><div className="card-body"><input className="input mb-3" value={noteTitle} onChange={(e)=>setNoteTitle(e.target.value)} placeholder="笔记标题（可选）"/><textarea className="textarea min-h-52" value={noteBody} onChange={(e)=>setNoteBody(e.target.value)} placeholder="记录假设、证据、推断、风险和后续验证事项。"/><div className="mt-3 flex justify-end gap-2">{editingNote&&<button className="btn" onClick={()=>{setEditingNote(null);setNoteTitle("");setNoteBody("")}}>取消编辑</button>}<button className="btn btn-primary" disabled={!noteBody.trim()||saveNote.isPending} onClick={()=>saveNote.mutate()}><Save size={16}/>{editingNote?"保存版本":"添加笔记"}</button></div></div></div>
          <div className="card"><div className="card-header"><h2 className="section-title">项目资料</h2><span className="badge">{detailQuery.data.items.length}</span></div><div className="max-h-[420px] divide-y divide-slate-100 overflow-y-auto">{detailQuery.data.items.length?detailQuery.data.items.map((item)=><div key={item.id} className="flex items-center gap-3 p-4"><FileText size={18} className="shrink-0 text-blue-700"/><div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{item.title_override??item.object_id}</div><div className="mt-1 text-xs text-slate-400">{item.object_type} · {new Date(item.created_at).toLocaleDateString("zh-CN")}</div></div><button className="btn btn-ghost btn-danger !px-2" onClick={()=>deleteItem.mutate(item.id)}><Trash2 size={15}/></button></div>):<p className="p-8 text-center text-sm text-slate-500">从其他页面选择“加入项目”后显示在这里。</p>}</div></div>
        </section>
        <section className="card"><div className="card-header"><h2 className="section-title">笔记历史</h2><span className="badge">{detailQuery.data.notes.length}</span></div><div className="divide-y divide-slate-100">{detailQuery.data.notes.length?detailQuery.data.notes.map((note)=><article key={note.id} className="p-5"><div className="flex items-start justify-between gap-3"><div><h3 className="font-bold">{note.title??"研究笔记"}</h3><div className="mt-1 text-xs text-slate-400">版本 {note.version_no} · 更新 {new Date(note.updated_at).toLocaleString("zh-CN")}</div></div><div className="flex gap-2"><button className="btn !min-h-8 !px-3 !text-xs" onClick={()=>editNote(note)}>编辑</button><button className="btn btn-ghost btn-danger !min-h-8 !px-2" onClick={()=>deleteNote.mutate(note.id)}><Trash2 size={15}/></button></div></div><p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">{note.body_markdown}</p></article>):<p className="p-8 text-center text-sm text-slate-500">尚无笔记。</p>}</div></section>
      </>:null}</main>
    </div>}
  </div>;
}

export default function WorkspacePage(){return <Suspense fallback={<LoadingBlock/>}><WorkspaceContent/></Suspense>;}
