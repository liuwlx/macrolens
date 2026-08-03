"use client";

import { Filter, PanelLeftOpen, PanelRightOpen, RotateCcw } from "lucide-react";

import type { SeriesBrowserFacets } from "@/lib/types";

import type { BrowserState } from "./browser-query";

type Props = {
  state: BrowserState;
  facets?: SeriesBrowserFacets;
  onChange(patch: Partial<BrowserState>): void;
  onReset(): void;
  onOpenFilters(): void;
  onOpenTree(): void;
  onOpenDetail(): void;
};

const labels: Record<keyof SeriesBrowserFacets, string> = {
  provider: "数据来源",
  theme: "主题分类",
  frequency: "频率",
  unit: "单位",
  seasonal_adjustment: "季调",
};

export function BrowserFilterBar({ state, facets, onChange, onReset, onOpenFilters, onOpenTree, onOpenDetail }: Props) {
  return (
    <section className="data-browser-filter" aria-label="数据筛选">
      <div className="data-browser-mobile-tools">
        <button className="btn" type="button" onClick={onOpenTree}><PanelLeftOpen size={16} />指标树</button>
        <button className="btn" type="button" onClick={onOpenFilters}><Filter size={16} />筛选</button>
        <span className="flex-1" />
        <button className="btn" type="button" onClick={onOpenDetail} disabled={!state.series}><PanelRightOpen size={16} />指标详情</button>
      </div>
      <div className="data-browser-filter-grid">
        {(Object.keys(labels) as Array<keyof SeriesBrowserFacets>).map((key) => (
          <label className="data-browser-filter-field" key={key}>
            <span>{labels[key]}</span>
            <select className="select" value={state[key]} onChange={(event) => onChange({ [key]: event.target.value })}>
              <option value="">全部{labels[key].replace("数据", "")}</option>
              {(facets?.[key] ?? []).map((item) => <option value={item.value} key={item.value}>{item.label}（{item.count}）</option>)}
            </select>
          </label>
        ))}
        <fieldset className="data-browser-date-filter">
          <legend>发布时间</legend>
          <input aria-label="开始日期" className="input" type="date" value={state.published_from} onChange={(event) => onChange({ published_from: event.target.value })} />
          <span aria-hidden="true">—</span>
          <input aria-label="结束日期" className="input" type="date" value={state.published_to} onChange={(event) => onChange({ published_to: event.target.value })} />
        </fieldset>
        <button className="btn data-browser-reset" type="button" onClick={onReset}><RotateCcw size={15} />重置筛选</button>
      </div>
      <div className="data-browser-filter-summary"><Filter size={14} />筛选结果会同步到地址栏，可复制链接恢复当前研究视图。</div>
    </section>
  );
}
