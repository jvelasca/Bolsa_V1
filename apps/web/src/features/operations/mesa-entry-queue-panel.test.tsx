import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MesaEntryQueuePanel } from "@/features/operations/mesa-entry-queue-panel";

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({ effectiveAccountId: "acc-1" }),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getDecisionBoard: vi.fn(async () => ({
      data: {
        accountId: "acc-1",
        generatedAt: "2026-08-25T12:00:00Z",
        buckets: {
          pendingConfirm: 0,
          vetoed: 0,
          deferred: 0,
          autoWaiting: 0,
          total: 2,
        },
        semiF3Queue: [],
        decisionSessions: [
          {
            sessionId: "s1",
            kind: "propose",
            status: "open",
            instrumentId: "i1",
            symbol: "AAA",
            createdAt: "2026-08-25T11:00:00Z",
            gate: "PASS",
            tradePlan: {
              artifactType: "ART-TRADE-PLAN",
              schemaVersion: "1.0.0",
              decisionId: "d1",
              instrumentId: "i1",
              direction: "long",
              status: "ARMED",
              entryReady: false,
              structuralStop: 9,
              entry: 10,
            },
          },
          {
            sessionId: "s2",
            kind: "propose",
            status: "open",
            instrumentId: "i2",
            symbol: "BBB",
            createdAt: "2026-08-25T10:00:00Z",
            gate: "VETO",
            tradePlan: {
              artifactType: "ART-TRADE-PLAN",
              schemaVersion: "1.0.0",
              decisionId: "d2",
              instrumentId: "i2",
              direction: "long",
              status: "BLOCKED",
              entryReady: false,
              structuralStop: 9,
              entry: 10,
            },
          },
        ],
      },
    })),
  },
}));

function renderPanel(entriesBlocked = false) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MesaEntryQueuePanel entriesBlocked={entriesBlocked} />
    </QueryClientProvider>,
  );
}

afterEach(() => cleanup());

describe("MesaEntryQueuePanel P4.2 filters", () => {
  it("renders filter controls and filters by symbol", async () => {
    renderPanel();
    expect(await screen.findByTestId("mesa-entry-queue-filters")).toBeTruthy();
    expect(screen.getByTestId("mesa-entry-queue-symbol")).toBeTruthy();
    expect(await screen.findByText("AAA")).toBeTruthy();
    expect(screen.getByText("BBB")).toBeTruthy();

    fireEvent.change(screen.getByTestId("mesa-entry-queue-symbol"), {
      target: { value: "bbb" },
    });
    await waitFor(() => {
      expect(screen.queryByText("AAA")).toBeNull();
      expect(screen.getByText("BBB")).toBeTruthy();
    });
  });

  it("filters by gate VETO", async () => {
    renderPanel();
    await screen.findByText("AAA");
    fireEvent.change(screen.getByTestId("mesa-entry-queue-gate"), {
      target: { value: "VETO" },
    });
    await waitFor(() => {
      expect(screen.queryByText("AAA")).toBeNull();
      expect(screen.getByText("BBB")).toBeTruthy();
    });
  });

  it("ARMED row shows Preparar operación (same CTA as Mercado/Hoy)", async () => {
    renderPanel();
    expect(
      await screen.findByTestId("mesa-entry-action-AAA"),
    ).toHaveTextContent("Preparar operación");
    expect(screen.getByTestId("mesa-entry-action-AAA").textContent).not.toMatch(
      /comprar/i,
    );
  });

  it("entriesBlocked → Entradas bloqueadas on every row", async () => {
    renderPanel(true);
    expect(
      await screen.findByTestId("mesa-entry-action-AAA"),
    ).toHaveTextContent("Entradas bloqueadas");
    expect(screen.getByTestId("mesa-entry-action-BBB")).toHaveTextContent(
      "Entradas bloqueadas",
    );
  });
});
