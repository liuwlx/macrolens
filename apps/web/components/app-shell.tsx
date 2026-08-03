"use client";

import {
  Bell,
  BookOpenText,
  Bot,
  CalendarDays,
  ChartNoAxesCombined,
  ChevronLeft,
  FileBarChart,
  FolderKanban,
  Home,
  Landmark,
  Menu,
  Search,
  Settings2,
  ShieldCheck,
  Star,
  TableProperties,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { FormEvent, ReactNode, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/components/auth-provider";
import { apiFetch } from "@/lib/api";
import type { Notification } from "@/lib/types";

const navigation = [
  { href: "/", label: "首页", icon: Home },
  { href: "/data", label: "数据总览", icon: TableProperties },
  { href: "/calendar", label: "发布日历", icon: CalendarDays },
  { href: "/fomc", label: "FOMC中心", icon: Landmark },
  { href: "/compare", label: "对比分析", icon: ChartNoAxesCombined },
  { href: "/documents", label: "文档检索", icon: BookOpenText },
  { href: "/ai", label: "AI分析", icon: Bot },
  { href: "/workspace", label: "研究工作台", icon: FolderKanban },
  { href: "/favorites", label: "收藏夹", icon: Star },
  { href: "/alerts", label: "提醒中心", icon: Bell },
  { href: "/reports", label: "报告中心", icon: FileBarChart },
];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [search, setSearch] = useState("");
  const navItems = user?.role === "admin" ? [...navigation, { href: "/admin", label: "系统管理", icon: ShieldCheck }] : navigation;
  const notifications = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => apiFetch<Notification[]>("/me/notifications?unread_only=true"),
    refetchInterval: 60_000,
  });

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    const query = search.trim();
    if (query) router.push(`/data?q=${encodeURIComponent(query)}`);
  }

  const Sidebar = ({ mobile = false }: { mobile?: boolean }) => (
    <aside
      className={`${mobile ? "fixed inset-y-0 left-0 z-50 shadow-2xl" : "fixed inset-y-0 left-0 z-30 desktop-only"} flex flex-col border-r border-slate-200 bg-white transition-all ${collapsed && !mobile ? "w-[76px]" : "w-[222px]"}`}
    >
      <div className="flex h-[68px] items-center gap-3 border-b border-slate-200 px-5">
        <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-blue-700 text-white shadow-sm">
          <Landmark size={19} />
        </div>
        {(!collapsed || mobile) && <div><strong className="text-[15px] text-blue-900">MacroLens</strong><div className="text-xs text-slate-500">宏观镜</div></div>}
        {mobile && <button aria-label="关闭导航" className="ml-auto btn btn-ghost !min-h-8 !px-2" onClick={() => setMobileOpen(false)}><X size={18} /></button>}
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              title={collapsed && !mobile ? item.label : undefined}
              onClick={() => setMobileOpen(false)}
              className={`flex h-11 items-center gap-3 rounded-lg px-3 text-sm font-medium transition ${active ? "bg-blue-50 text-blue-700" : "text-slate-600 hover:bg-slate-50 hover:text-slate-900"}`}
            >
              <item.icon size={19} className="shrink-0" />
              {(!collapsed || mobile) && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>
      {!mobile && (
        <button className="flex h-12 items-center gap-3 border-t border-slate-200 px-6 text-sm text-slate-500 hover:bg-slate-50" onClick={() => setCollapsed(!collapsed)}>
          <ChevronLeft size={18} className={collapsed ? "rotate-180" : ""} />
          {!collapsed && "收起"}
        </button>
      )}
    </aside>
  );

  return (
    <div className="min-h-screen bg-[#f5f7fb]">
      <Sidebar />
      {mobileOpen && <><div className="fixed inset-0 z-40 bg-slate-950/30 md:hidden" onClick={() => setMobileOpen(false)} /><Sidebar mobile /></>}
      <div className={`transition-all ${collapsed ? "md:ml-[76px]" : "md:ml-[222px]"}`}>
        <header className="sticky top-0 z-20 flex h-[68px] items-center gap-4 border-b border-slate-200 bg-white/95 px-4 backdrop-blur md:px-6">
          <button className="btn btn-ghost !px-2 md:hidden" onClick={() => setMobileOpen(true)} aria-label="打开导航"><Menu size={21} /></button>
          <form onSubmit={submitSearch} className="relative max-w-2xl flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
            <input value={search} onChange={(event) => setSearch(event.target.value)} className="input !pl-10" placeholder="搜索指标名称或官方序列号" />
          </form>
          <Link href="/alerts" className="relative grid size-10 place-items-center rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-50" aria-label="通知">
            <Bell size={18} />
            {!!notifications.data?.length && <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-red-500 px-1 text-center text-[10px] font-bold leading-5 text-white">{Math.min(notifications.data.length, 99)}</span>}
          </Link>
          <div className="hidden items-center gap-3 md:flex">
            <div className="grid size-9 place-items-center rounded-full bg-blue-100 font-bold text-blue-700">{user?.display_name.slice(0, 1)}</div>
            <div className="max-w-36"><div className="truncate text-sm font-semibold">{user?.display_name}</div><div className="truncate text-xs text-slate-500">{user?.email}</div></div>
            <button className="btn btn-ghost !px-2" title="退出登录" onClick={() => void logout()}><Settings2 size={17} /></button>
          </div>
        </header>
        <main className="mx-auto max-w-[1720px] p-4 pb-24 md:p-6 md:pb-8">{children}</main>
      </div>
      <nav className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-center justify-around border-t border-slate-200 bg-white md:hidden">
        {navItems.slice(0, 5).map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return <Link key={item.href} href={item.href} className={`flex min-w-14 flex-col items-center gap-1 text-[10px] ${active ? "text-blue-700" : "text-slate-500"}`}><item.icon size={19}/>{item.label.slice(0,4)}</Link>;
        })}
      </nav>
    </div>
  );
}
