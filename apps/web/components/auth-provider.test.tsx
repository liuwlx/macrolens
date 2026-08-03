import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { User } from "@/lib/types";

import { AuthProvider, useAuth } from "./auth-provider";

const authApi = vi.hoisted(() => ({
  currentUser: null as User | null,
  fetch: vi.fn(),
}));

vi.mock("@/lib/api", () => {
  class ApiError extends Error {
    constructor(message: string, public readonly status: number) {
      super(message);
    }
  }
  return { ApiError, apiFetch: authApi.fetch };
});

const userA: User = { id: "user-a", email: "a@example.test", display_name: "A", role: "researcher" };
const userB: User = { id: "user-b", email: "b@example.test", display_name: "B", role: "researcher" };

function PrivateRunsProbe() {
  const { user, loading, login, logout } = useAuth();
  const runs = useQuery({
    queryKey: ["ai-runs"],
    queryFn: () => authApi.fetch("/ai/runs?limit=50") as Promise<Array<{ id: string; prompt: string }>>,
    enabled: Boolean(user),
    staleTime: 30_000,
  });

  async function switchAccount() {
    await logout();
    await login(userB.email, "password-for-b");
  }

  return <div>
    <span>{loading ? "loading" : user?.email ?? "anonymous"}</span>
    <span>{runs.data?.[0]?.prompt ?? "no-runs"}</span>
    <button type="button" onClick={() => void switchAccount()}>switch account</button>
  </div>;
}

describe("AuthProvider private cache isolation", () => {
  beforeEach(() => {
    authApi.currentUser = userA;
    authApi.fetch.mockReset();
    authApi.fetch.mockImplementation(async (path: string) => {
      if (path === "/auth/me") return authApi.currentUser;
      if (path === "/auth/logout") {
        authApi.currentUser = null;
        return undefined;
      }
      if (path === "/auth/login") {
        authApi.currentUser = userB;
        return { user: userB };
      }
      if (path === "/ai/runs?limit=50") {
        return authApi.currentUser?.id === userA.id
          ? [{ id: "run-a", prompt: "user A confidential run" }]
          : [{ id: "run-b", prompt: "user B private run" }];
      }
      throw new Error(`Unexpected API path: ${path}`);
    });
  });

  it("does not render user A cached data after switching to user B", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: 30_000 } } });
    render(<QueryClientProvider client={client}><AuthProvider><PrivateRunsProbe /></AuthProvider></QueryClientProvider>);

    expect(await screen.findByText(userA.email)).toBeInTheDocument();
    expect(await screen.findByText("user A confidential run")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "switch account" }));

    expect(await screen.findByText(userB.email)).toBeInTheDocument();
    expect(await screen.findByText("user B private run")).toBeInTheDocument();
    expect(screen.queryByText("user A confidential run")).not.toBeInTheDocument();
    await waitFor(() => expect(authApi.fetch).toHaveBeenCalledWith("/ai/runs?limit=50"));
    expect(authApi.fetch.mock.calls.filter(([path]) => path === "/ai/runs?limit=50")).toHaveLength(2);
  });
});
