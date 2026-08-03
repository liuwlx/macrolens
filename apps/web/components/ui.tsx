"use client";

import { AlertCircle, Inbox, LoaderCircle, RefreshCw } from "lucide-react";
import { ReactNode } from "react";

export function LoadingBlock({ label = "正在加载..." }: { label?: string }) {
  return <div className="card flex min-h-48 items-center justify-center gap-3 text-slate-500"><LoaderCircle className="animate-spin" size={20}/>{label}</div>;
}

export function EmptyState({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return <div className="card flex min-h-52 flex-col items-center justify-center p-8 text-center"><Inbox className="mb-3 text-slate-300" size={36}/><h3 className="mb-1 font-semibold">{title}</h3><p className="mb-4 max-w-md text-sm text-slate-500">{description}</p>{action}</div>;
}

export function ErrorState({ message, retry }: { message: string; retry?: () => void }) {
  return <div className="card flex min-h-48 flex-col items-center justify-center p-8 text-center"><AlertCircle className="mb-3 text-red-400" size={34}/><h3 className="mb-1 font-semibold">加载失败</h3><p className="mb-4 text-sm text-slate-500">{message}</p>{retry && <button className="btn" onClick={retry}><RefreshCw size={16}/>重试</button>}</div>;
}

export function StatCard({ label, value, subtext, trend, icon }: { label: string; value: ReactNode; subtext?: string; trend?: number | null; icon?: ReactNode }) {
  return <div className="card p-4"><div className="mb-3 flex items-center justify-between text-sm text-slate-500"><span>{label}</span>{icon}</div><div className="text-2xl font-bold tracking-tight">{value}</div><div className="mt-2 flex items-center gap-2 text-xs"><span className={trend == null ? "text-slate-500" : trend >= 0 ? "negative" : "positive"}>{trend == null ? "—" : `${trend >= 0 ? "+" : ""}${trend.toFixed(2)}`}</span><span className="text-slate-400">{subtext}</span></div></div>;
}
