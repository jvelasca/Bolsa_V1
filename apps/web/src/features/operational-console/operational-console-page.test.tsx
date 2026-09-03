import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { OperationalConsolePage } from "@/features/operational-console/operational-console-page";

vi.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: undefined, isLoading: false, isError: false }),
}));

vi.mock("@/features/accounts/use-active-account", () => ({
  useActiveAccount: () => ({
    effectiveAccountId: "acc-1",
    account: { id: "acc-1", name: "Demo" },
    isLoading: false,
  }),
}));

vi.mock("@/features/operational-console/use-ops-self-eval", () => ({
  useOpsSelfEval: () => ({
    data: { portfolioReconciliation: { status: "ok" } },
    isLoading: false,
    isError: false,
    isFetching: false,
    refetch: vi.fn(),
  }),
  portfolioReconStatusFromReport: () => "clean",
}));

vi.mock("@/features/operational-console/use-estudio-auto-telemetry", () => ({
  useEstudioAutoTelemetry: () => ({
    data: { data: null },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
}));

vi.mock("@/features/operational-console/use-lifecycle-outbox-stats", () => ({
  useLifecycleOutboxStats: () => ({
    data: {
      pending: 0,
      processing: 0,
      dead: 0,
      oldestPendingAgeSeconds: null,
      oldestProcessingAgeSeconds: null,
      oldestDeadAgeSeconds: null,
      slaBreached: false,
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/features/operational-console/use-lifecycle-reconciliation", () => ({
  useLifecycleReconciliation: () => ({
    data: {
      accountId: "acc-1",
      status: "clean",
      checked: 0,
      driftCount: 0,
      lagCount: 0,
      blockedCount: 0,
      issues: [],
    },
    isLoading: false,
    isError: false,
  }),
}));

vi.mock("@/features/operations/mesa-incident-banner", () => ({
  MesaIncidentBanner: () => null,
}));

vi.mock("@/features/operational-console/operational-console-sections", () => ({
  OpsReadinessSection: () => <div data-testid="ops-readiness" />,
  OpsRuntimeSection: () => <div data-testid="ops-runtime" />,
  OpsSelfEvalSection: () => <div data-testid="ops-self-eval" />,
  OpsEstudioAutoSection: () => <div data-testid="ops-estudio-auto" />,
  OpsReconSection: () => <div data-testid="ops-recon" />,
  OpsLifecycleOutboxSection: () => <div data-testid="ops-lifecycle-outbox" />,
  OpsLifecycleReconSection: () => <div data-testid="ops-lifecycle-recon" />,
}));

vi.mock("@/features/operational-console/ops-incidents-and-links", () => ({
  OpsIncidentsSection: () => <div data-testid="ops-incidents" />,
  OpsQuickLinksSection: () => <div data-testid="ops-quick-links" />,
}));

describe("OperationalConsolePage V1.55", () => {
  it("surfaces exceptions first; technical sections in details", () => {
    render(
      <MemoryRouter>
        <OperationalConsolePage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId("operational-console")).toBeTruthy();
    expect(screen.getByTestId("ops-recon")).toBeTruthy();
    expect(screen.getByTestId("ops-incidents")).toBeTruthy();
    expect(screen.getByText(/Resolver excepciones/i)).toBeTruthy();
    expect(screen.getByText(/Ver detalles técnicos/i)).toBeTruthy();
  });
});
