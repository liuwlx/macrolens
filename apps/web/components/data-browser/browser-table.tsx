"use client";

import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Columns3, Download, RefreshCw } from "lucide-react";
import { KeyboardEvent } from "react";

import type { SeriesBrowserItem, SeriesBrowserResponse } from "@/lib/types";

import { formatMetric, formatNumber, metricTitle, metricTone, periodLabel } from "./browser-format";
import type { BrowserSort, BrowserState } from "./browser-query";

type Props = {
  state: BrowserState;
  data?: SeriesBrowserResponse;
  isLoading: boolean;
  isFetching: boolean;
  error?: Error | null;
  onRetry(): void;
  onRefresh(): void;
  onExport(): void;
  onSelect(item: SeriesBrowserItem): void;
  onSort(sort: BrowserSort): void;
  onPage(page: number): void;
};

const sortableColumns: Array<{ key: BrowserSort; label: string }> = [
  { key: "name", label: "项目" },
  { key: "current", label: "本期" },
  { key: "change", label: "变动" },
  { key: "period_change", label: "期间变化" },
  { key: "yoy", label: "同比" },
];

function SortButton({ column, state, onSort }: { column: { key: BrowserSort; label: string }; state: BrowserState; onSort(sort: BrowserSort): void }) {
  const active = state.sort === column.key;
  return <button type="button" className="data-browser-sort" onClick={() => onSort(column.key)}>{column.label}{active ? state.order === "asc" ? <ChevronUp size={12} /> : <ChevronDown size={12} /> : null}</button>;
}

export function BrowserTable({ state, data, isLoading, isFetching, error, onRetry, onRefresh, onExport, onSelect, onSort, onPage }: Props) {
  const totalPages = Math.max(1, Math.ceil((data?.pagination.total ?? 0) / (data?.pagination.limit ?? 20)));
  const rows = data?.items ?? [];

  function rowKeyDown(event: KeyboardEvent<HTMLTableRowElement>, item: SeriesBrowserItem) {
    if (event.key === "Enter") {
      event.preventDefault();
      onSelect(item);
    }
  }

  return (
    <section className="data-browser-card data-browser-table-card" aria-labelledby="browser-table-title">
      <header className="data-browser-card-header">
        <div><h2 id="browser-table-title">明细数据表</h2><p>同一数据快照 · 共 {data?.pagination.total ?? 0} 条</p></div>
        <div className="data-browser-toolbar">
          <button type="button" className="btn" onClick={onRefresh} aria-label="刷新明细表"><RefreshCw className={isFetching ? "animate-spin" : ""} size={15} />刷新</button>
          <button type="button" className="btn" title="使用当前验收列配置"><Columns3 size={15} />列设置</button>
          <button type="button" className="btn" onClick={onExport} disabled={!rows.length}><Download size={15} />下载表格</button>
        </div>
      </header>
      <div className="data-browser-table-wrap">
        <table className="data-browser-table">
          <thead><tr>
            {sortableColumns.slice(0, 2).map((column) => <th key={column.key} aria-sort={state.sort === column.key ? state.order === "asc" ? "ascending" : "descending" : "none"}><SortButton column={column} state={state} onSort={onSort} /></th>)}
            <th>上期</th>
            {sortableColumns.slice(2).map((column) => <th key={column.key} aria-sort={state.sort === column.key ? state.order === "asc" ? "ascending" : "descending" : "none"}><SortButton column={column} state={state} onSort={onSort} /></th>)}
            <th>单位</th><th>频率</th><th>来源</th>
          </tr></thead>
          <tbody>
            {isLoading && Array.from({ length: 10 }, (_, index) => <tr key={index} aria-hidden="true"><td colSpan={9}><div className="skeleton h-4" /></td></tr>)}
            {!isLoading && error && <tr><td colSpan={9}><div className="data-browser-inline-state"><strong>明细表加载失败</strong><span>{error.message}</span><button className="btn" onClick={onRetry}>重试</button></div></td></tr>}
            {!isLoading && !error && !rows.length && <tr><td colSpan={9}><div className="data-browser-inline-state"><strong>没有匹配指标</strong><span>调整筛选条件，或清空搜索后重试。</span></div></td></tr>}
            {!isLoading && !error && rows.map((item) => {
              const decimals = item.series.decimal_places ?? 2;
              const selected = state.series === item.series.id;
              const availability = item.availability === "not_ingested"
                ? <span className="badge badge-yellow">尚未采集</span>
                : item.availability === "not_available_as_of"
                  ? <span className="badge badge-yellow">该快照不可用</span>
                  : null;
              return <tr key={item.series.id} tabIndex={0} aria-selected={selected} className={selected ? "is-selected" : ""} onClick={() => onSelect(item)} onKeyDown={(event) => rowKeyDown(event, item)}>
                <td className="data-browser-name-cell"><span className="data-browser-row-caret">›</span><span><strong>{item.series.name_zh}</strong><small>{item.series.canonical_code}</small></span></td>
                <td className="font-semibold" title={item.current?.period_start ?? undefined}>{item.display_denied ? <span className="badge badge-yellow">展示受限</span> : availability ?? formatNumber(item.current?.value, decimals)}</td>
                <td title={item.previous?.period_start ?? undefined}>{item.display_denied ? "—" : formatNumber(item.previous?.value, decimals)}</td>
                <td className={metricTone(item.change)} title={metricTitle(item.change)}>{formatMetric(item.change, decimals)}</td>
                <td className={metricTone(item.period_change)} title={metricTitle(item.period_change)}><span className="sr-only">{periodLabel(item.period_change.basis)}：</span>{formatMetric(item.period_change, decimals)}</td>
                <td className={metricTone(item.yoy)} title={metricTitle(item.yoy)}>{formatMetric(item.yoy, decimals)}</td>
                <td>{item.series.unit_label_zh || item.series.unit_code}</td>
                <td>{item.series.frequency}</td>
                <td>{item.series.provider?.code ?? "—"}</td>
              </tr>;
            })}
          </tbody>
        </table>
      </div>
      <footer className="data-browser-pagination">
        <span>显示 {rows.length ? (state.page - 1) * 20 + 1 : 0}–{Math.min(state.page * 20, data?.pagination.total ?? 0)}，共 {data?.pagination.total ?? 0} 条</span>
        <div><button className="btn" type="button" aria-label="上一页" onClick={() => onPage(state.page - 1)} disabled={state.page <= 1}><ChevronLeft size={15} /></button><span>第 {state.page} / {totalPages} 页</span><button className="btn" type="button" aria-label="下一页" onClick={() => onPage(state.page + 1)} disabled={state.page >= totalPages}><ChevronRight size={15} /></button></div>
      </footer>
    </section>
  );
}
