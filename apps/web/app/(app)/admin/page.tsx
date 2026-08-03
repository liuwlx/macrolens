"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity, Ban, CheckCircle2, Database, FileText, Play, RefreshCw, ServerCog, ShieldCheck, TriangleAlert, UserPlus } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/page-header";
import { ErrorState, LoadingBlock, StatCard } from "@/components/ui";
import { apiFetch } from "@/lib/api";

type ProviderRow = { id:number; code:string; name:string; provider_type:string; license_class:string; redistribution_ok:boolean; active:boolean };
type JobRow = { id:string; job_type:string; status:string; attempts:number; max_attempts:number; last_error?:string|null; created_at:string };
type MappingRow = { id:number; canonical_code:string; name_zh:string; provider_code:string; dataset_code:string; provider_series_id?:string|null; mapping_status:string; is_primary:boolean };
type QualityRow = { id:number; rule_code:string; severity:string; passed:boolean; message?:string|null; checked_at:string };
type UserRow = { id:string; email:string; display_name:string; role:string; active:boolean; last_login_at?:string|null; created_at:string };

export default function AdminPage() {
  const queryClient = useQueryClient();
  const [provider, setProvider] = useState("FRED_API");
  const [documentProvider,setDocumentProvider]=useState("FED");
  const [documentUrl,setDocumentUrl]=useState("");
  const [documentTitle,setDocumentTitle]=useState("");
  const [newUserEmail,setNewUserEmail]=useState("");
  const [newUserName,setNewUserName]=useState("");
  const [newUserPassword,setNewUserPassword]=useState("");
  const [newUserRole,setNewUserRole]=useState("researcher");
  const providers = useQuery({ queryKey:["admin","providers"], queryFn:()=>apiFetch<ProviderRow[]>("/admin/providers") });
  const jobs = useQuery({ queryKey:["admin","jobs"], queryFn:()=>apiFetch<JobRow[]>("/admin/jobs?limit=100"), refetchInterval:10000 });
  const mappings = useQuery({ queryKey:["admin","mappings"], queryFn:()=>apiFetch<MappingRow[]>("/admin/source-mappings?limit=500") });
  const quality = useQuery({ queryKey:["admin","quality"], queryFn:()=>apiFetch<QualityRow[]>("/admin/quality-results?passed=false&limit=100") });
  const users = useQuery({ queryKey:["admin","users"], queryFn:()=>apiFetch<UserRow[]>("/admin/users") });
  const enqueue = useMutation({
    mutationFn:()=>apiFetch("/admin/jobs",{method:"POST",body:JSON.stringify({job_type:"sync_provider",payload:{provider_code:provider,mode:"incremental"},idempotency_key:`manual-sync:${provider}:${Date.now()}`,priority:20})}),
    onSuccess:()=>void queryClient.invalidateQueries({queryKey:["admin","jobs"]}),
  });
  const retry = useMutation({ mutationFn:(id:string)=>apiFetch(`/admin/jobs/${id}/retry`,{method:"POST"}),onSuccess:()=>void queryClient.invalidateQueries({queryKey:["admin","jobs"]}) });
  const fetchDocument=useMutation({
    mutationFn:()=>apiFetch("/admin/documents/fetch",{method:"POST",body:JSON.stringify({provider_code:documentProvider,source_url:documentUrl,title:documentTitle,title_zh:documentTitle,document_type:"official_release",language:"en",copyright_status:"official"})}),
    onSuccess:()=>{setDocumentUrl("");setDocumentTitle("");void queryClient.invalidateQueries({queryKey:["admin","jobs"]});},
  });
  const createUser=useMutation({
    mutationFn:()=>apiFetch<UserRow>("/admin/users",{method:"POST",body:JSON.stringify({email:newUserEmail,display_name:newUserName,password:newUserPassword,role:newUserRole})}),
    onSuccess:()=>{setNewUserEmail("");setNewUserName("");setNewUserPassword("");setNewUserRole("researcher");void queryClient.invalidateQueries({queryKey:["admin","users"]});},
  });
  const updateUser=useMutation({
    mutationFn:({id,active}:{id:string;active:boolean})=>apiFetch<UserRow>(`/admin/users/${id}`,{method:"PATCH",body:JSON.stringify({active})}),
    onSuccess:()=>void queryClient.invalidateQueries({queryKey:["admin","users"]}),
  });

  if (providers.isLoading || jobs.isLoading || mappings.isLoading || quality.isLoading || users.isLoading) return <LoadingBlock label="加载运营数据..."/>;
  const error=providers.error||jobs.error||mappings.error||quality.error||users.error;
  if(error)return <ErrorState message={(error as Error).message} retry={()=>{void providers.refetch();void jobs.refetch();void mappings.refetch();void quality.refetch();void users.refetch();}}/>;
  const failed=jobs.data?.filter((item)=>item.status==="failed")??[];
  const pending=mappings.data?.filter((item)=>item.mapping_status!=="verified")??[];

  return <div>
    <PageHeader title="系统管理 / 数据运营控制台" description="管理用户、数据源映射、同步任务、文档采集与质量门禁。" actions={<button className="btn" onClick={()=>{void providers.refetch();void jobs.refetch();void mappings.refetch();void quality.refetch();void users.refetch();}}><RefreshCw size={16}/>刷新</button>}/>
    <section className="grid-auto mb-5"><StatCard label="启用数据源" value={providers.data?.filter((x)=>x.active).length??0} icon={<ServerCog size={18}/>} /><StatCard label="待审核映射" value={pending.length} icon={<Database size={18}/>} /><StatCard label="失败任务" value={failed.length} icon={<TriangleAlert size={18}/>} /><StatCard label="阻断质量问题" value={quality.data?.filter((x)=>!x.passed&&x.severity==="blocking").length??0} icon={<ShieldCheck size={18}/>} /></section>
    <section className="card mb-5"><div className="card-header"><div><h2 className="section-title">手动同步</h2><p className="mt-1 text-xs text-slate-500">任务使用独立幂等键进入PostgreSQL队列。</p></div></div><div className="card-body flex flex-col gap-3 md:flex-row"><select className="select" value={provider} onChange={(e)=>setProvider(e.target.value)}>{providers.data?.filter((x)=>x.active).map((x)=><option value={x.code} key={x.code}>{x.code} · {x.name}</option>)}</select><button className="btn btn-primary" disabled={enqueue.isPending} onClick={()=>enqueue.mutate()}><Play size={16}/>立即同步</button></div></section>
    <section className="card mb-5"><div className="card-header"><div><h2 className="section-title">采集官方文档</h2><p className="mt-1 text-xs text-slate-500">仅接受公开 HTTPS 地址；系统会下载、版本化、解析、切块并建立语义索引。</p></div></div><div className="card-body grid gap-3 lg:grid-cols-[180px_1fr_1fr_auto]"><select className="select" value={documentProvider} onChange={(e)=>setDocumentProvider(e.target.value)}>{providers.data?.filter((x)=>x.active).map((x)=><option value={x.code} key={x.code}>{x.code}</option>)}</select><input className="input" value={documentTitle} onChange={(e)=>setDocumentTitle(e.target.value)} placeholder="文档标题"/><input className="input" value={documentUrl} onChange={(e)=>setDocumentUrl(e.target.value)} placeholder="https://官方文档地址"/><button className="btn btn-primary" disabled={!documentTitle.trim()||!documentUrl.trim()||fetchDocument.isPending} onClick={()=>fetchDocument.mutate()}><FileText size={16}/>{fetchDocument.isPending?"排队中":"开始采集"}</button></div>{fetchDocument.isError&&<div className="px-5 pb-4 text-sm text-red-600">{(fetchDocument.error as Error).message}</div>}</section>
    <section className="card mb-5"><div className="card-header"><div><h2 className="section-title">用户与访问权限</h2><p className="mt-1 text-xs text-slate-500">生产环境默认关闭公开注册，由管理员创建账号。</p></div><span className="badge">{users.data?.length??0}</span></div><div className="card-body grid gap-3 lg:grid-cols-[1fr_1fr_1fr_160px_auto]"><input className="input" value={newUserEmail} onChange={(e)=>setNewUserEmail(e.target.value)} placeholder="邮箱"/><input className="input" value={newUserName} onChange={(e)=>setNewUserName(e.target.value)} placeholder="显示名称"/><input className="input" type="password" value={newUserPassword} onChange={(e)=>setNewUserPassword(e.target.value)} placeholder="至少12位临时密码"/><select className="select" value={newUserRole} onChange={(e)=>setNewUserRole(e.target.value)}><option value="researcher">研究员</option><option value="admin">管理员</option></select><button className="btn btn-primary" disabled={!newUserEmail||!newUserName||newUserPassword.length<12||createUser.isPending} onClick={()=>createUser.mutate()}><UserPlus size={16}/>创建用户</button></div>{createUser.isError&&<div className="px-5 pb-4 text-sm text-red-600">{(createUser.error as Error).message}</div>}<div className="table-wrap"><table className="table"><thead><tr><th>用户</th><th>角色</th><th>状态</th><th>最近登录</th><th/></tr></thead><tbody>{users.data?.map((item)=><tr key={item.id}><td><div className="font-semibold">{item.display_name}</div><div className="text-xs text-slate-400">{item.email}</div></td><td>{item.role}</td><td><span className={`badge ${item.active?"badge-green":"badge-red"}`}>{item.active?"启用":"停用"}</span></td><td>{item.last_login_at?new Date(item.last_login_at).toLocaleString("zh-CN"):"—"}</td><td><button className={`btn !min-h-8 !px-3 ${item.active?"btn-danger":""}`} disabled={updateUser.isPending} onClick={()=>updateUser.mutate({id:item.id,active:!item.active})}>{item.active?<Ban size={14}/>:<CheckCircle2 size={14}/>} {item.active?"停用":"启用"}</button></td></tr>)}</tbody></table></div></section>
    <div className="grid gap-5 xl:grid-cols-2">
      <section className="card"><div className="card-header"><h2 className="section-title">最近任务</h2><span className="badge">{jobs.data?.length??0}</span></div><div className="max-h-[520px] overflow-auto"><table className="table"><thead><tr><th>任务</th><th>状态</th><th>尝试</th><th>创建时间</th><th/></tr></thead><tbody>{jobs.data?.map((job)=><tr key={job.id}><td><div className="font-semibold">{job.job_type}</div>{job.last_error&&<div className="max-w-72 truncate text-xs text-red-500">{job.last_error}</div>}</td><td><span className={`badge ${job.status==="succeeded"?"badge-green":job.status==="failed"?"badge-red":"badge-blue"}`}>{job.status}</span></td><td>{job.attempts}/{job.max_attempts}</td><td>{new Date(job.created_at).toLocaleString("zh-CN")}</td><td>{job.status==="failed"&&<button className="btn !min-h-8 !px-3" onClick={()=>retry.mutate(job.id)}><RefreshCw size={14}/>重试</button>}</td></tr>)}</tbody></table></div></section>
      <section className="card"><div className="card-header"><h2 className="section-title">待审核数据源映射</h2><span className="badge">{pending.length}</span></div><div className="max-h-[520px] overflow-auto"><table className="table"><thead><tr><th>指标</th><th>来源</th><th>序列</th><th>状态</th></tr></thead><tbody>{pending.slice(0,200).map((row)=><tr key={row.id}><td><div className="font-semibold">{row.name_zh}</div><div className="text-xs text-slate-400">{row.canonical_code}</div></td><td>{row.provider_code}<div className="text-xs text-slate-400">{row.dataset_code}</div></td><td>{row.provider_series_id??"待元数据发现"}</td><td><span className="badge">{row.mapping_status}</span></td></tr>)}</tbody></table></div></section>
    </div>
    {!!quality.data?.length&&<section className="card mt-5"><div className="card-header"><h2 className="section-title">未通过质量规则</h2></div><div className="divide-y divide-slate-100">{quality.data.map((row)=><div key={row.id} className="flex items-start gap-3 p-4"><Activity className="mt-0.5 text-red-500" size={18}/><div><div className="font-semibold">{row.rule_code} · {row.severity}</div><div className="mt-1 text-sm text-slate-500">{row.message??"未提供详细信息"}</div></div></div>)}</div></section>}
  </div>;
}
