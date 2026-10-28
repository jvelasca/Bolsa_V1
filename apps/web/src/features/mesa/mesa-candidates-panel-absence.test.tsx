/**
 * P1-05 — sin ranking legible no se afirma «Universo 0» ni se acusa al usuario.
 *
 * Falsable: con `(funnel?.universeCount ?? 0) < 20`, un error de estudios/scan
 * pintaba «Universo 0 · Operables 0» y el CTA «Tu universo de análisis es
 * pequeño», atribuyendo al usuario la causa de un dato que no se leyó.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import type { OpportunityRankingV1 } from "@bolsa/shared";
import { MesaCandidatesPanel } from "@/features/mesa/mesa-candidates-panel";

vi.mock("@/stores/supervised-f3-queue-store", () => ({
  useSupervisedF3QueueStore: (selector: (s: { items: unknown[] }) => unknown) =>
    selector({ items: [] }),
}));

vi.mock("@/features/trading/use-pending-orders", () => ({
  usePendingOrders: () => ({ pendingOrders: [], isError: false }),
}));

function ranking(universeCount: number, top = 0): OpportunityRankingV1 {
  return {
    funnel: {
      universeCount,
      screenedCount: 0,
      hitCount: 0,
      analyzedCount: 0,
      setupCount: 0,
      portfolioFitCount: 0,
      operableCount: 0,
      asOf: null,
      marketDataAsOf: null,
      analysisAsOf: null,
      rankingAsOf: null,
      universeListId: null,
      scanStale: false,
      provisional: true,
    },
    top: [],
    all: [],
    discovered: [],
    maxQuality: top,
  } as unknown as OpportunityRankingV1;
}

function renderPanel(props: {
  rankingUnavailable?: boolean;
  rankingLoading?: boolean;
  rankingValue?: OpportunityRankingV1;
}) {
  return render(
    <QueryClientProvider
      client={
        new QueryClient({ defaultOptions: { queries: { retry: false } } })
      }
    >
      <MemoryRouter>
        <MesaCandidatesPanel
          ranking={props.rankingValue ?? ranking(0)}
          entriesBlocked={false}
          rankingUnavailable={props.rankingUnavailable}
          rankingLoading={props.rankingLoading}
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

afterEach(cleanup);

describe("Mesa · oportunidades — universo ausente", () => {
  it("con el ranking caído declara el hueco y no acusa de universo pequeño", () => {
    renderPanel({ rankingUnavailable: true });

    expect(screen.getByTestId("mesa-ranking-absence")).toHaveTextContent(
      "No disponible",
    );
    expect(screen.queryByText("Tu universo de análisis es pequeño")).toBeNull();
    expect(screen.queryByTestId("mesa-universe-cta")).toBeNull();
    expect(screen.queryByTestId("mesa-no-operations")).toBeNull();
    expect(screen.queryByText(/Universo 0/)).toBeNull();
  });

  it("mientras carga no diagnostica", () => {
    renderPanel({ rankingLoading: true });

    expect(screen.getByTestId("mesa-ranking-absence")).toHaveAttribute(
      "data-absence-state",
      "loading",
    );
    expect(screen.queryByTestId("mesa-universe-cta")).toBeNull();
    expect(screen.queryByTestId("mesa-no-operations")).toBeNull();
  });

  it("con un universo medido y pequeño sí emite el CTA", () => {
    renderPanel({ rankingValue: ranking(5) });

    expect(screen.getByTestId("mesa-universe-cta")).toHaveTextContent(
      "Tu universo de análisis es pequeño",
    );
    expect(screen.queryByTestId("mesa-ranking-absence")).toBeNull();
  });

  it("con un universo medido suficiente no hay CTA ni vacío falso", () => {
    renderPanel({ rankingValue: ranking(40) });

    expect(screen.queryByTestId("mesa-universe-cta")).toBeNull();
    expect(screen.queryByTestId("mesa-ranking-absence")).toBeNull();
    expect(screen.getByTestId("mesa-no-operations")).toBeTruthy();
  });
});
