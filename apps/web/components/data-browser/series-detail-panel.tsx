"use client";

import { Bot, CalendarClock, Download, GitCompareArrows, History, Star } from "lucide-react";

import type { AICapabilitiesResponse, SeriesAnalyticsResponse, SeriesBrowserItem, SeriesDetail } from "@/lib/types";

import { formatLocalDate, formatNumber } from "./browser-format";

type Props = {
  item?: SeriesBrowserItem;
  detail?: SeriesDetail;
  analytics?: SeriesAnalyticsResponse;
  ai?: AICapabilitiesResponse;
  isLoading: boolean;
  isFavorite: boolean;
  favoritePending: boolean;
  onFavorite(): void;
  onHistory(): void;
  onCompare(): void;
  onExport(): void;
  onAI(): void;
};

export function SeriesDetailPanel({ item, detail, analytics, ai, isLoading, isFavorite, favoritePending, onFavorite, onHistory, onCompare, onExport, onAI }: Props) {
  const series = detail ?? item?.series;
  if (isLoading && !series) return <aside className="data-browser-card data-browser-detail-card"><div className="p-4 space-y-3"><div className="skeleton h-5" /><div className="skeleton h-16" /><div className="skeleton h-48" /></div></aside>;
  if (!series || !item) return <aside className="data-browser-card data-browser-detail-card"><div className="data-browser-inline-state"><strong>选择一个指标</strong><span>从指标树或明细表选择后查看详细信息。</span></div></aside>;

  const downloadAllowed = item.license?.download_allowed === true && analytics?.capabilities.download.allowed !== false;
  const aiAllowed = ai?.allowed === true && analytics?.capabilities.ai.allowed !== false;
  const nextRelease = analytics?.next_release;
  return <aside className="data-browser-card data-browser-detail-card" aria-labelledby="series-detail-title">
    <header className="data-browser-card-header"><div><h2 id="series-detail-title">指标详情</h2><p>{series.canonical_code}</p></div><button className={`btn ${isFavorite ? "btn-primary" : ""}`} type="button" onClick={onFavorite} disabled={favoritePending} aria-pressed={isFavorite}><Star size={15} fill={isFavorite ? "currentColor" : "none"} />{isFavorite ? "已收藏" : "收藏"}</button></header>
    <div className="data-browser-detail-body">
      <div className="data-browser-current-value"><span>{series.name_zh}</span><strong>{item.display_denied ? "受限" : formatNumber(item.current?.value, "decimal_places" in series ? series.decimal_places : 2)} <small>{series.unit_label_zh}</small></strong><p>最新期：{item.current?.period_start ?? "—"}</p></div>
      <dl className="data-browser-definition-list">
        <div><dt>指标定义</dt><dd>{"description" in series && series.description ? series.description : "暂无指标定义。"}</dd></div>
        <div><dt>数据来源</dt><dd>{series.provider?.name ?? series.provider?.code ?? "—"}</dd></div>
        <div><dt>频率</dt><dd>{series.frequency}</dd></div>
        <div><dt>单位</dt><dd>{series.unit_label_zh || series.unit_code}</dd></div>
        <div><dt>季节调整</dt><dd>{"seasonal_adjustment" in series ? series.seasonal_adjustment || "—" : "—"}</dd></div>
        <div><dt>下次发布</dt><dd>{nextRelease ? <span title={`${nextRelease.source_timezone} · UTC ${new Date(nextRelease.scheduled_at).toISOString()}`}>{formatLocalDate(nextRelease.scheduled_at, true)}</span> : "暂无已确认发布时间"}</dd></div>
      </dl>
      <div className="data-browser-tags"><span className="badge">{series.theme}</span><span className="badge">{series.frequency}</span><span className="badge">{series.provider?.code ?? "官方来源"}</span></div>
      <div className="data-browser-detail-actions">
        <button type="button" className="btn btn-primary" onClick={onHistory}><History size={15} />查看历史数据</button>
        <button type="button" className="btn" onClick={onCompare}><GitCompareArrows size={15} />加入对比</button>
        <button type="button" className="btn" onClick={onExport} disabled={!downloadAllowed} title={downloadAllowed ? "导出当前范围" : analytics?.capabilities.download.reason ?? "当前许可不允许下载"}><Download size={15} />导出数据</button>
        <button type="button" className="btn" onClick={onAI} disabled={!aiAllowed} title={aiAllowed ? "在 AI 页面附加该指标" : ai?.reason ?? analytics?.capabilities.ai.reason ?? "AI 上下文不可用"}><Bot size={15} />加入 AI 上下文</button>
      </div>
      {nextRelease && <div className="data-browser-next-release"><CalendarClock size={16} /><span><strong>{nextRelease.title_zh}</strong><small>{nextRelease.role} · {nextRelease.status}</small></span></div>}
    </div>
  </aside>;
}
