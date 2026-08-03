"use client";

import { X } from "lucide-react";
import { KeyboardEvent, ReactNode, useEffect, useRef } from "react";

type DrawerKind = "tree" | "filters" | "detail" | null;

type Props = {
  open: DrawerKind;
  title: string;
  children: ReactNode;
  onClose(): void;
};

export function BrowserDrawer({ open, title, children, onClose }: Props) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement as HTMLElement | null;
    panel.current?.focus();
    function escape(event: globalThis.KeyboardEvent) { if (event.key === "Escape") onClose(); }
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("keydown", escape); previous?.focus(); };
  }, [open, onClose]);

  if (!open) return null;
  function trap(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "Tab") return;
    const items = panel.current?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])');
    if (!items?.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  }
  return <div className="data-browser-drawer-layer" role="presentation"><button className="data-browser-drawer-backdrop" type="button" aria-label="关闭面板" onClick={onClose} /><div className={`data-browser-drawer ${open === "detail" ? "is-detail" : ""}`} role="dialog" aria-modal="true" aria-labelledby="data-browser-drawer-title" tabIndex={-1} ref={panel} onKeyDown={trap}><header><h2 id="data-browser-drawer-title">{title}</h2><button className="btn btn-ghost" type="button" onClick={onClose} aria-label={`关闭${title}`}><X size={18} /></button></header><div className="data-browser-drawer-content">{children}</div></div></div>;
}
