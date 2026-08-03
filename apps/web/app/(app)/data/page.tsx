"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

import { useAuth } from "@/components/auth-provider";
import { DataBrowserPage } from "@/components/data-browser/data-browser-page";
import { LegacyDataPage } from "@/components/data-browser/legacy-data-page";
import { LoadingBlock } from "@/components/ui";

function DataPageGate() {
  const params = useSearchParams();
  const { user, loading } = useAuth();
  if (loading) return <LoadingBlock label="正在准备数据浏览器..." />;
  const enabled = process.env.NEXT_PUBLIC_DATA_BROWSER_V2 === "true";
  const admin = user?.role === "admin";
  const requested = params.get("view");
  const showV2 = enabled ? !(requested === "v1" && admin) : requested === "v2" && admin;
  return showV2 ? <DataBrowserPage /> : <LegacyDataPage />;
}

export default function DataPage() {
  return <Suspense fallback={<LoadingBlock label="正在加载数据页面..." />}><DataPageGate /></Suspense>;
}
