"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Download, LineChart, Plus, Save, Search, Trash2 } from "lucide-react";
import { Suspense, useEffect, useMemo, useState } from "react";

import { TimeSeriesChart } from "@/components/chart";
import { PageHeader } from "@/components/page-header";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui";
import { apiFetch } from "@/lib/api";
import type { CompareResponse, SavedView, SeriesSummary } from "@/lib/types";

type Selected = { series: SeriesSummary; transform: string; axis: "left"|"right"; lag_periods: number };
const transformOptions = [["level","原始值"],["difference","变动"],["mom","环比"],["yoy","同比"],["annualized_3m","3个月年化"],["annualized_6m","6个月年化"],["rebased_100","基期100"],["zscore","标准分数"]];

function CompareContent(){
  const queryClient=useQueryClient();
  const searchParams=useSearchParams();
  const [query,setQuery]=useState("");
  const [selected,setSelected]=useState<Selected[]>([]);
  const [start,setStart]=useState("2019-01-01");
  const [end,setEnd]=useState("");
  const seriesQuery=useQuery({queryKey:["series","compare",query],queryFn:()=>apiFetch<{items:SeriesSummary[]}>(`/series?q=${encodeURIComponent(query)}&limit=100`)});
  const viewsQuery=useQuery({queryKey:["saved-views","compare"],queryFn:()=>apiFetch<SavedView[]>("/me/saved-views?view_type=compare")});
  const compare=useMutation({mutationFn:()=>apiFetch<CompareResponse>("/compare/query",{method:"POST",body:JSON.stringify({series:selected.map((item)=>({series_id:item.series.id,transform:item.transform,axis:item.axis,lag_periods:item.lag_periods})),start:start||null,end:end||null,vintage:"latest",include_correlation:true})})});
  const save=useMutation({mutationFn:()=>{
    const proposed=selected.map((item)=>item.series.name_zh).join(" vs ")||"未命名对比视图";
    const name=window.prompt("保存视图名称",proposed)?.trim();
    if(!name) throw new Error("已取消保存");
    return apiFetch<SavedView>("/me/saved-views",{method:"POST",body:JSON.stringify({name,view_type:"compare",definition:{series:selected,start,end}})});
  },onSuccess:async()=>{await queryClient.invalidateQueries({queryKey:["saved-views","compare"]});}});
  const removeView=useMutation({mutationFn:(id:string)=>apiFetch(`/me/saved-views/${id}`,{method:"DELETE"}),onSuccess:async()=>{await queryClient.invalidateQueries({queryKey:["saved-views","compare"]});}});

  const selectedIds=useMemo(()=>new Set(selected.map((item)=>item.series.id)),[selected]);
  function add(item:SeriesSummary){if(selected.length>=8||selectedIds.has(item.id))return;setSelected((prev)=>[...prev,{series:item,transform:item.default_transform||"level",axis:prev.length>2?"right":"left",lag_periods:0}]);}
  function update(id:string,patch:Partial<Selected>){setSelected((prev)=>prev.map((item)=>item.series.id===id?{...item,...patch}:item));}
  function restoreView(view:SavedView){
    const definition=view.definition;
    if(Array.isArray(definition.series)) setSelected(definition.series.slice(0,8));
    setStart(typeof definition.start==="string"?definition.start:"");
    setEnd(typeof definition.end==="string"?definition.end:"");
  }
  useEffect(()=>{
    const viewId=searchParams.get("view");
    const view=viewsQuery.data?.find((item)=>item.id===viewId);
    if(view) restoreView(view);
  },[searchParams,viewsQuery.data]);
  const comparisonDownloadAllowed = Boolean(compare.data?.items.length) && compare.data!.items.every((item) => item.license?.download_allowed === true);
  function exportCsv() {
    if (!compare.data || !comparisonDownloadAllowed) return;
    const dates = Array.from(
      new Set(compare.data.items.flatMap((item) => item.data.map((point) => point.period_start))),
    ).sort();
    const bySeries = compare.data.items.map(
      (item) => new Map(item.data.map((point) => [point.period_start, point.value] as const)),
    );
    const lines = [
      ["period", ...compare.data.items.map((item) => `${item.series.canonical_code}:${item.transform}`)].join(","),
      ...dates.map((date) => [date, ...bySeries.map((values) => values.get(date) ?? "")].join(",")),
    ];
    const blob = new Blob(["\uFEFF" + lines.join("\n")], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "macrolens-comparison.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  return <div>
    <PageHeader title="对比分析 / 多指标研究工作室" description="对齐不同频率与单位，进行同比、基期化、标准化、滞后和相关性分析。" actions={<><button className="btn" disabled={!selected.length||save.isPending} onClick={()=>save.mutate()}><Save size={16}/>{save.isSuccess?"已保存":"保存视图"}</button><button className="btn" disabled={!compare.data||!comparisonDownloadAllowed} title={compare.data&&!comparisonDownloadAllowed?"至少一个数据源许可不允许下载":"导出对比结果"} onClick={exportCsv}><Download size={16}/>导出CSV</button><button className="btn btn-primary" disabled={!selected.length||compare.isPending} onClick={()=>compare.mutate()}><LineChart size={16}/>运行分析</button></>}/>
    <div className="grid gap-5 xl:grid-cols-[310px_minmax(0,1fr)]">
      <aside className="space-y-5">
        <div className="card"><div className="card-header"><h2 className="section-title">选择指标</h2><span className="badge">{selected.length}/8</span></div><div className="card-body"><label className="relative"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400"/><input className="input !pl-9" value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="搜索指标"/></label><div className="mt-3 max-h-72 space-y-1 overflow-y-auto">{seriesQuery.data?.items.map((item)=><button key={item.id} disabled={selectedIds.has(item.id)||selected.length>=8} onClick={()=>add(item)} className="flex w-full items-center justify-between gap-2 rounded-lg p-2 text-left text-sm hover:bg-slate-50 disabled:opacity-40"><span className="min-w-0"><span className="block truncate font-semibold">{item.name_zh}</span><span className="block truncate text-xs text-slate-400">{item.canonical_code}</span></span><Plus size={15}/></button>)}</div></div></div>
        <div className="card"><div className="card-header"><h2 className="section-title">分析区间</h2></div><div className="card-body space-y-3"><label className="text-xs text-slate-500">开始<input className="input mt-1" type="date" value={start} onChange={(event)=>setStart(event.target.value)}/></label><label className="text-xs text-slate-500">结束<input className="input mt-1" type="date" value={end} onChange={(event)=>setEnd(event.target.value)}/></label></div></div>
        <div className="card"><div className="card-header"><h2 className="section-title">已保存视图</h2><span className="badge">{viewsQuery.data?.length??0}</span></div><div className="card-body space-y-2">{viewsQuery.isLoading?<p className="text-xs text-slate-500">正在加载...</p>:viewsQuery.data?.length?viewsQuery.data.map((view)=><div key={view.id} className="flex items-center gap-2 rounded-lg border border-slate-200 p-2"><button className="min-w-0 flex-1 text-left" onClick={()=>restoreView(view)}><span className="block truncate text-sm font-semibold">{view.name}</span><span className="text-xs text-slate-400">{new Date(view.updated_at).toLocaleString("zh-CN")}</span></button><button className="btn btn-ghost btn-danger !min-h-8 !px-2" aria-label={`删除${view.name}`} onClick={()=>removeView.mutate(view.id)}><Trash2 size={14}/></button></div>):<p className="text-xs text-slate-500">尚未保存对比视图。</p>}</div></div>
      </aside>
      <main className="min-w-0 space-y-5">
        <section className="card"><div className="card-header"><div><h2 className="section-title">指标配置</h2><p className="mt-1 text-xs text-slate-500">右轴适合与左轴单位不同的指标；滞后为正表示序列向后平移。</p></div></div>{selected.length?<div className="table-wrap"><table className="data-table"><thead><tr><th>指标</th><th>变换</th><th>坐标轴</th><th>滞后期</th><th></th></tr></thead><tbody>{selected.map((item)=><tr key={item.series.id}><td><div className="font-semibold">{item.series.name_zh}</div><div className="text-xs text-slate-400">{item.series.unit_label_zh} · {item.series.frequency}</div></td><td><select className="select !min-h-8 !w-36" value={item.transform} onChange={(event)=>update(item.series.id,{transform:event.target.value})}>{transformOptions.map(([value,label])=><option key={value} value={value}>{label}</option>)}</select></td><td><select className="select !min-h-8 !w-24" value={item.axis} onChange={(event)=>update(item.series.id,{axis:event.target.value as "left"|"right"})}><option value="left">左轴</option><option value="right">右轴</option></select></td><td><input className="input !min-h-8 !w-24" type="number" min={-120} max={120} value={item.lag_periods} onChange={(event)=>update(item.series.id,{lag_periods:Number(event.target.value)})}/></td><td><button className="btn btn-ghost btn-danger !min-h-8 !px-2" onClick={()=>setSelected((prev)=>prev.filter((x)=>x.series.id!==item.series.id))}><Trash2 size={15}/></button></td></tr>)}</tbody></table></div>:<div className="p-10 text-center text-sm text-slate-500">从左侧添加最多8个指标。</div>}</section>
        {compare.isPending?<LoadingBlock label="正在对齐时间序列并计算相关性..."/>:compare.isError?<ErrorState message={(compare.error as Error).message} retry={()=>compare.mutate()}/>:compare.data?<>
          <section className="card"><div className="card-header"><div><h2 className="section-title">对比走势图</h2><p className="mt-1 text-xs text-slate-500">数据截至 {new Date(compare.data.data_as_of).toLocaleString("zh-CN")}</p></div></div><div className="card-body"><TimeSeriesChart height={440} series={compare.data.items.map((item)=>({name:`${item.series.name_zh} · ${item.transform}${item.lag_periods?` · lag ${item.lag_periods}`:""}`,data:item.data,axis:item.axis==="right"?1:0}))}/></div></section>
          <section className="card"><div className="card-header"><h2 className="section-title">相关性矩阵</h2></div><div className="table-wrap"><table className="data-table"><thead><tr><th>指标A</th><th>指标B</th><th>相关系数</th><th>共同观测数</th></tr></thead><tbody>{compare.data.correlations.map((cell,index)=>{const left=compare.data.items.find((item)=>item.series.id===cell.left_series_id);const right=compare.data.items.find((item)=>item.series.id===cell.right_series_id);return <tr key={index}><td>{left?.series.name_zh}</td><td>{right?.series.name_zh}</td><td className="font-bold">{cell.coefficient==null?"—":cell.coefficient.toFixed(3)}</td><td>{cell.observations}</td></tr>})}</tbody></table></div></section>
        </>:<EmptyState title="配置后运行分析" description="后端会读取同一vintage口径，执行频率变换、滞后和平滑对齐。"/>}
      </main>
    </div>
  </div>;
}

export default function ComparePage(){return <Suspense fallback={<LoadingBlock/>}><CompareContent/></Suspense>;}
