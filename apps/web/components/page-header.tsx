import { ReactNode } from "react";

export function PageHeader({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-col justify-between gap-3 lg:flex-row lg:items-end">
      <div><h1 className="page-title">{title}</h1><p className="page-description">{description}</p></div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
