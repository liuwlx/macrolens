"use client";

import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenText, CalendarClock, ChartNoAxesCombined, FolderKanban, Landmark, Search, Star, Trash2 } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { AIRun, DocumentSummary, Favorite, FomcMeeting, Project, ReleaseEvent, SeriesSummary } from "@/lib/types";

function resourcePath(favorite:Favorite){switch(favorite.object_type){case"series":return`/series/${favorite.object_id}`;case"document":return`/documents/${favorite.object_id}`;case"release_event":return`/release-events/${favorite.object_id}`;case"fomc_meeting":return`/fomc/meetings/${favorite.object_id}`;case"project":return`/me/projects/${favorite.object_id}`;case"ai_run":return`/ai/runs/${favorite.object_id}`;default:return null;}}
function displayName(type:string,data:unknown,fallback:string){const d=data as Record<string,unknown>|undefined;if(!d)return fallback;if(type==="series")return String(d.name_zh??fallback);if(type==="document")return String(d.title_zh??d.title??fallback);if(type==="release_event")return String(d.title_zh??fallback);if(type==="fomc_meeting")return `FOMC会议 ${d.meeting_end??fallback}`;if(type==="project")return String(d.name??fallback);if(type==="ai_run")return String(d.prompt??fallback);return fallback;}
function targetHref(favorite:Favorite){switch(favorite.object_type){case"series":return`/data?series=${favorite.object_id}`;case"document":return`/documents?document=${favorite.object_id}`;case"release_event":return`/calendar?event=${favorite.object_id}`;case"fomc_meeting":return`/fomc?meeting=${favorite.object_id}`;case"project":return`/workspace?project=${favorite.object_id}`;case"ai_run":return`/ai?run=${favorite.object_id}`;case"saved_view":return`/compare?view=${favorite.object_id}`;default:return"/favorites";}}
const icons:Record<string,typeof Star>={series:ChartNoAxesCombined,document:BookOpenText,release_event:CalendarClock,fomc_meeting:Landmark,project:FolderKanban,ai_run:Star,saved_view:ChartNoAxesCombined};

export default function FavoritesPage(){
  const client=useQueryClient();const[query,setQuery]=useState("");const[type,setType]=useState("");
  const favoritesQuery=useQuery({queryKey:["favorites"],queryFn:()=>apiFetch<Favorite[]>("/me/favorites")});
  const details=useQueries({queries:(favoritesQuery.data??[]).map((favorite)=>{const path=resourcePath(favorite);return{queryKey:["favorite-detail",favorite.object_type,favorite.object_id],queryFn:()=>path?apiFetch<SeriesSummary|DocumentSummary|ReleaseEvent|FomcMeeting|Project|AIRun>(path):Promise.resolve(null),enabled:Boolean(path),retry:false}})});
  const remove=useMutation({mutationFn:(id:string)=>apiFetch(`/me/favorites/${id}`,{method:"DELETE"}),onSuccess:()=>void client.invalidateQueries({queryKey:["favorites"]})});
  const rows=useMemo(()=>{return(favoritesQuery.data??[]).map((favorite,index)=>({favorite,data:details[index]?.data,name:displayName(favorite.object_type,details[index]?.data,favorite.note??favorite.object_id)})).filter((item)=>(!type||item.favorite.object_type===type)&&(!query||item.name.toLowerCase().includes(query.toLowerCase())||item.favorite.note?.toLowerCase().includes(query.toLowerCase())));},[favoritesQuery.data,details,type,query]);
  const types=Array.from(new Set((favoritesQuery.data??[]).map((item)=>item.object_type)));

  return <div><PageHeader title="收藏夹 / 研究观察清单" description="集中管理指标、文档、事件、会议、项目、AI分析和保存的对比视图。"/>
    <div className="card mb-5 p-4"><div className="grid gap-3 md:grid-cols-[1fr_200px]"><label className="relative"><Search size={17} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><input className="input !pl-10" value={query} onChange={(e)=>setQuery(e.target.value)} placeholder="搜索收藏名称或备注"/></label><select className="select" value={type} onChange={(e)=>setType(e.target.value)}><option value="">全部类型</option>{types.map((item)=><option key={item} value={item}>{item}</option>)}</select></div></div>
    {favoritesQuery.isLoading?<LoadingBlock/>:favoritesQuery.isError?<ErrorState message={(favoritesQuery.error as Error).message} retry={()=>void favoritesQuery.refetch()}/>:!rows.length?<EmptyState title="收藏夹是空的" description="在指标、文档、发布或FOMC页面点击收藏，稍后在这里统一管理。"/>:<div className="grid-auto">{rows.map(({favorite,name})=>{const Icon=icons[favorite.object_type]??Star;return <article key={favorite.id} className="card flex flex-col p-5"><div className="flex items-start gap-3"><div className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700"><Icon size={19}/></div><div className="min-w-0 flex-1"><span className="badge">{favorite.object_type}</span><h2 className="mt-2 line-clamp-2 font-bold leading-6">{name}</h2><p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-500">{favorite.note??"未添加备注"}</p></div></div><div className="mt-auto flex items-center justify-between border-t border-slate-100 pt-4 text-xs text-slate-400"><span>{favorite.group_name??"未分组"} · {new Date(favorite.created_at).toLocaleDateString("zh-CN")}</span><div className="flex gap-2"><Link className="btn !min-h-8 !px-3 !text-xs" href={targetHref(favorite)}>打开</Link><button className="btn btn-ghost btn-danger !min-h-8 !px-2" onClick={()=>remove.mutate(favorite.id)}><Trash2 size={15}/></button></div></div></article>})}</div>}
  </div>;
}
