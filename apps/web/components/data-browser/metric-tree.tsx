"use client";

import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, Circle, Folder, Search } from "lucide-react";
import { KeyboardEvent, useMemo, useState } from "react";

import { apiFetch, queryString } from "@/lib/api";
import type { TaxonomyBrowserNode, TaxonomyBrowserSeries, TaxonomyChildrenResponse } from "@/lib/types";

import type { BrowserState } from "./browser-query";

type Props = {
  state: BrowserState;
  onNode(nodeId: string): void;
  onSeries(series: TaxonomyBrowserSeries, nodeId: string | null): void;
};

type BranchProps = Props & { parentId: string | null; depth: number; query: string; scopeAll: boolean };

function treePath(state: BrowserState, parentId: string | null, query: string, scopeAll: boolean) {
  return `/taxonomies/macro-default/children${queryString({
    parent_id: parentId,
    q: query,
    scope: scopeAll ? "all" : undefined,
    provider: state.provider,
    theme: state.theme,
    frequency: state.frequency,
    unit: state.unit,
    seasonal_adjustment: state.seasonal_adjustment,
  })}`;
}

function TreeBranch({ state, parentId, depth, query, scopeAll, onNode, onSeries }: BranchProps) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const children = useQuery({
    queryKey: ["taxonomy-children", "macro-default", parentId, query, scopeAll, state.provider, state.theme, state.frequency, state.unit, state.seasonal_adjustment],
    queryFn: ({ signal }) => apiFetch<TaxonomyChildrenResponse>(treePath(state, parentId, query, scopeAll), { signal }),
    staleTime: 5 * 60_000,
    retry: (count, error) => !("status" in (error as object)) && count < 1,
  });

  function toggle(node: TaxonomyBrowserNode) {
    setExpanded((previous) => {
      const next = new Set(previous);
      if (next.has(node.id)) next.delete(node.id); else next.add(node.id);
      return next;
    });
  }

  function keyDown(event: KeyboardEvent<HTMLButtonElement>, node: TaxonomyBrowserNode) {
    if (event.key === "ArrowRight" && node.has_children && !expanded.has(node.id)) { event.preventDefault(); toggle(node); }
    if (event.key === "ArrowLeft" && expanded.has(node.id)) { event.preventDefault(); toggle(node); }
    if (event.key === "Enter") { event.preventDefault(); onNode(node.id); }
    if (event.key === "Home" || event.key === "End") {
      event.preventDefault();
      const group = event.currentTarget.closest('[role="group"]');
      const items = group?.querySelectorAll<HTMLButtonElement>('[role="treeitem"]');
      items?.[event.key === "Home" ? 0 : items.length - 1]?.focus();
    }
  }

  if (children.isLoading) return <div className="space-y-2 p-2" aria-label="正在加载指标树">{Array.from({ length: depth ? 3 : 7 }, (_, index) => <div className="skeleton h-7" key={index} />)}</div>;
  if (children.isError) return <div className="data-browser-tree-error">指标树加载失败<button className="btn" onClick={() => void children.refetch()}>重试</button></div>;

  return <div role={depth === 0 ? "tree" : "group"} aria-label={depth === 0 ? "宏观指标树" : undefined}>
    {(children.data?.nodes ?? []).map((node) => {
      const open = expanded.has(node.id);
      return <div key={node.id}>
        <button
          type="button"
          role="treeitem"
          aria-level={depth + 1}
          aria-expanded={node.has_children ? open : undefined}
          aria-selected={state.node === node.id}
          className={`data-browser-tree-row ${state.node === node.id ? "is-selected" : ""}`}
          style={{ paddingInlineStart: `${10 + depth * 18}px` }}
          onKeyDown={(event) => keyDown(event, node)}
          onClick={() => { onNode(node.id); if (node.has_children) toggle(node); }}
        >
          {node.has_children ? open ? <ChevronDown size={14} /> : <ChevronRight size={14} /> : <span className="size-[14px]" />}
          <Folder size={15} className="text-amber-500" />
          <span className="truncate">{node.name_zh}</span>
          <small>{node.descendant_series_count}</small>
        </button>
        {open && <TreeBranch {...{ state, onNode, onSeries, query, scopeAll }} parentId={node.id} depth={depth + 1} />}
      </div>;
    })}
    {(children.data?.series ?? []).map((series) => <button key={series.id} type="button" role="treeitem" aria-level={depth + 1} aria-selected={state.series === series.id} className={`data-browser-tree-row data-browser-tree-series ${state.series === series.id ? "is-selected" : ""}`} style={{ paddingInlineStart: `${28 + depth * 18}px` }} onClick={() => onSeries(series, parentId)}><Circle size={7} fill="currentColor" /><span className="truncate">{series.name_zh}</span></button>)}
  </div>;
}

export function MetricTree({ state, onNode, onSeries }: Props) {
  const [query, setQuery] = useState("");
  const [scopeAll, setScopeAll] = useState(false);
  const branchKey = useMemo(() => `${query}:${scopeAll}`, [query, scopeAll]);
  return <section className="data-browser-card data-browser-tree-card" aria-labelledby="metric-tree-title">
    <header className="data-browser-card-header"><div><h2 id="metric-tree-title">指标树</h2><p>按主题逐级浏览</p></div></header>
    <div className="data-browser-tree-search"><label><Search size={15} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索指标名称" aria-label="搜索指标名称" /></label><label className="data-browser-scope"><input type="checkbox" checked={scopeAll} onChange={(event) => setScopeAll(event.target.checked)} />搜索全部</label></div>
    <div className="data-browser-tree-scroll"><TreeBranch key={branchKey} {...{ state, onNode, onSeries, query, scopeAll }} parentId={null} depth={0} /></div>
  </section>;
}
