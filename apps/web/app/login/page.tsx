"use client";

import { Landmark, LoaderCircle } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { apiFetch } from "@/lib/api";

function safeNextPath(value: string | null): string {
  if (!value || !value.startsWith("/") || value.startsWith("//")) return "/";
  return value;
}

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const { login, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const registration = useQuery({ queryKey: ["auth-config"], queryFn: () => apiFetch<{ allow_public_registration: boolean }>("/auth/config") });

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (mode === "login") await login(email, password);
      else await register(email, displayName, password);
      router.replace(safeNextPath(params.get("next")));
    } catch (value) {
      setError(value instanceof Error ? value.message : "操作失败");
    } finally {
      setBusy(false);
    }
  }

  return <main className="grid min-h-screen place-items-center bg-[radial-gradient(circle_at_top_left,#eaf1ff,transparent_40%),#f6f8fc] p-5"><section className="card grid w-full max-w-5xl overflow-hidden lg:grid-cols-[1.1fr_.9fr]"><div className="hidden min-h-[620px] flex-col justify-between bg-blue-800 p-12 text-white lg:flex"><div className="flex items-center gap-3"><div className="grid size-11 place-items-center rounded-xl bg-white/15"><Landmark /></div><div><div className="text-xl font-bold">MacroLens</div><div className="text-sm text-blue-200">宏观镜</div></div></div><div><h1 className="max-w-xl text-4xl font-bold leading-tight">把权威数据、政策文件和研究判断放进同一张工作台。</h1><p className="mt-5 max-w-xl leading-7 text-blue-100">追踪宏观发布、历史修订与FOMC，使用可追溯引用的AI完成研究和报告。</p></div><p className="text-xs text-blue-200">生产环境请修改引导管理员密码，并启用Secure Cookie。</p></div><div className="flex min-h-[620px] items-center p-8 md:p-12"><div className="mx-auto w-full max-w-sm"><div className="mb-8 lg:hidden"><div className="flex items-center gap-3"><div className="grid size-10 place-items-center rounded-xl bg-blue-700 text-white"><Landmark size={20}/></div><strong>MacroLens · 宏观镜</strong></div></div><h2 className="text-2xl font-bold">{mode === "login" ? "欢迎回来" : "创建研究账号"}</h2><p className="mt-2 text-sm text-slate-500">登录后进入宏观研究工作区。</p><form onSubmit={submit} className="mt-8 space-y-4">{mode === "register" && <label className="block text-sm font-medium">显示名称<input className="input mt-2" value={displayName} onChange={(event) => setDisplayName(event.target.value)} required /></label>}<label className="block text-sm font-medium">邮箱<input type="email" className="input mt-2" value={email} onChange={(event) => setEmail(event.target.value)} required /></label><label className="block text-sm font-medium">密码<input type="password" className="input mt-2" value={password} onChange={(event) => setPassword(event.target.value)} minLength={12} required /></label>{error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}<button className="btn btn-primary w-full" disabled={busy}>{busy && <LoaderCircle className="animate-spin" size={17}/>} {mode === "login" ? "登录" : "注册"}</button></form>{(registration.data?.allow_public_registration || mode === "register") && <button className="mt-5 w-full text-sm font-medium text-blue-700" onClick={() => setMode(mode === "login" ? "register" : "login")}>{mode === "login" ? "没有账号？创建账号" : "已有账号？返回登录"}</button>}</div></div></section></main>;
}

export default function LoginPage(){return <Suspense fallback={<main className="grid min-h-screen place-items-center"><LoaderCircle className="animate-spin text-blue-700"/></main>}><LoginForm/></Suspense>;}
