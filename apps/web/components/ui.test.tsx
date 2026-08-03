import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EmptyState, ErrorState, StatCard } from "./ui";

describe("shared UI states", () => {
  it("renders an empty state action", () => {
    render(<EmptyState title="暂无数据" description="等待同步" action={<button>同步</button>} />);
    expect(screen.getByRole("heading", { name: "暂无数据" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "同步" })).toBeInTheDocument();
  });

  it("runs retry from the error state", () => {
    const retry = vi.fn();
    render(<ErrorState message="网络错误" retry={retry} />);
    fireEvent.click(screen.getByRole("button", { name: /重试/ }));
    expect(retry).toHaveBeenCalledOnce();
  });

  it("formats positive stat trends", () => {
    render(<StatCard label="核心PCE" value="2.6%" trend={0.1} subtext="同比" />);
    expect(screen.getByText("+0.10")).toBeInTheDocument();
  });
});
