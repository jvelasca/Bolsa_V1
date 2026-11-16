/**
 * Pestaña **Vigilancia** (ADR-050) — contrato de presentación.
 *
 * Se mockean los hooks: aquí se comprueba que la vista NO maquilla el veredicto
 * (`not_evaluated` se pinta «NO EVALUADO», nunca como PASS), que el R vivo va separado del
 * realizado y que un `409` de sellado se declara en vez de reintentarse.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { StrategyVerificationRunDto } from "@bolsa/shared";

const profileMock = vi.fn();
const overviewMock = vi.fn();
const ledgerMock = vi.fn();
const recomputeMock = vi.fn();

vi.mock("@/features/auto-monitor/use-strategy-verification", async () => {
  const actual = await vi.importActual<
    typeof import("@/features/auto-monitor/use-strategy-verification")
  >("@/features/auto-monitor/use-strategy-verification");
  return {
    ...actual,
    useStrategyVerificationProfile: () => profileMock(),
    useStrategyVerification: () => overviewMock(),
    useStrategyVerificationLedger: () => ledgerMock(),
    useRecomputeStrategyVerification: () => recomputeMock(),
  };
});

import { StrategyVerificationPanel } from "@/features/auto-monitor/strategy-verification-panel";

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

const PROFILE = {
  available: true,
  activationAllowed: false,
  profileHash: "f".repeat(64),
  notes: [],
  profile: {
    version: "StrategyVerificationProfileV1",
    profileId: "default",
    accountScope: "acc-1",
    universeInstruments: ["AAA", "BBB"],
    cadence: {
      mode: "epochs",
      everyDays: 30,
      anchorDay: null,
      rollingEnabled: true,
      rollingLookbackDays: 1,
    },
    samples: {
      minCohortSamples: 12,
      minClosedCycles: 1,
      minPerInstrumentCycles: 0,
      epochsInVerdict: 12,
    },
    arms: ["as_run", "hold_structural", "cash", "market_bh", "candidate"],
    candidate: {
      requirePointInTime: true,
      measureForward: true,
      maxCandidates: 1,
    },
    thresholds: {
      minExcessMeanR: 0,
      minShareEpochsNotWorse: 0.6,
      maxDrawdownPct: 15,
      minHitRate: null,
      maxEvidenceAgeDays: null,
    },
    decision: {
      version: "strategy-verification-decision-v1",
      watchOnInconclusive: true,
      relabOnArmDominance: true,
      allowAutoActivation: false,
    },
    execution: {},
  },
};

function runFixture(): StrategyVerificationRunDto {
  return {
    id: "run-1",
    accountId: "acc-1",
    profileId: "default",
    profileHash: "f".repeat(64),
    kind: "epoch",
    day: "2026-01-05",
    toDay: "2026-01-30",
    measurementHash: "a".repeat(64),
    verdict: "insufficient_sample",
    strategyVersion: "ver-1",
    createdAt: "2026-11-14T00:00:00+00:00",
    payload: {
      verdict: "insufficient_sample",
      activationAllowed: false,
      profileId: "default",
      profileHash: "f".repeat(64),
      gates: [
        { gate: "method_certified", status: "pass", reason: null },
        { gate: "observed_health", status: "not_evaluated", reason: null },
      ],
      samples: 1,
      requiredSamples: 12,
      asRunMeanR: 1.25,
      bestArm: "hold_structural",
      bestArmMeanR: 0.9,
      meanExcessR: 0.35,
      shareEpochsNotWorse: 1,
      bootstrapLow: null,
      candidateMeanReturnPct: null,
      asRunMeanReturnPct: 1.1,
      measurementHash: "a".repeat(64),
      reasons: ["insufficient_sample:1/12"],
      limits: [],
      epochs: [
        {
          epochId: "epoch:2026-01-05",
          day: "2026-01-05",
          toDay: "2026-01-30",
          artifactHash: "b".repeat(64),
          measured: true,
          certified: true,
          armsR: { as_run: 1.25, hold_structural: 0.9 },
          armsReturnPct: { as_run: 1.1 },
          closedCycles: 2,
          operations: 2,
          consistentDecisions: 2,
          inconsistentDecisions: 0,
          unrealizedR: 0.4,
          strategyVersion: "ver-1",
          mandateVersion: null,
          candidateMeasured: false,
          candidateReturnPct: null,
          candidateGap: "candidate_not_provided",
          certificationChecks: { artifact_integrity: "PASS" },
        },
      ],
    },
  };
}

describe("StrategyVerificationPanel", () => {
  it("declara que el veredicto es advisory y no activa nada", () => {
    profileMock.mockReturnValue({
      data: PROFILE,
      isFetching: false,
      refetch: vi.fn(),
    });
    overviewMock.mockReturnValue({
      data: {
        available: false,
        activationAllowed: false,
        latest: null,
        runs: [],
        notes: [],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    });
    ledgerMock.mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
    });
    recomputeMock.mockReturnValue({
      isPending: false,
      isSuccess: false,
      isError: false,
      mutate: vi.fn(),
    });

    render(<StrategyVerificationPanel />);

    expect(screen.getByTestId("verification-advisory").textContent).toContain(
      "no activa nada",
    );
    expect(screen.getByTestId("verification-profile").textContent).toContain(
      "cada 30 d",
    );
    expect(screen.getByTestId("verification-empty").textContent).toContain(
      "Sin veredictos",
    );
  });

  it("pinta not_evaluated como NO EVALUADO (nunca como PASS) y separa el R vivo", () => {
    profileMock.mockReturnValue({
      data: PROFILE,
      isFetching: false,
      refetch: vi.fn(),
    });
    overviewMock.mockReturnValue({
      data: {
        available: true,
        activationAllowed: false,
        latest: runFixture(),
        runs: [runFixture()],
        notes: [],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    });
    ledgerMock.mockReturnValue({
      data: {
        available: true,
        activationAllowed: false,
        day: "2026-01-05",
        rows: [],
        notes: [],
      },
      isLoading: false,
      isError: false,
    });
    recomputeMock.mockReturnValue({
      isPending: false,
      isSuccess: false,
      isError: false,
      mutate: vi.fn(),
    });

    render(<StrategyVerificationPanel />);

    expect(screen.getByTestId("verification-verdict-label").textContent).toBe(
      "MUESTRA INSUFICIENTE",
    );
    expect(
      screen.getByTestId("verification-gate-observed_health").textContent,
    ).toContain("NO EVALUADO");
    const epoch = screen.getByTestId("verification-epoch-2026-01-05");
    expect(epoch.textContent).toContain("1.25");
    // El R vivo se declara en su columna: no se suma al realizado.
    expect(epoch.textContent).toContain("0.4");
    expect(epoch.textContent).toContain("candidate_not_provided");
  });

  it("declara el 409 de sellado en vez de reintentar a ciegas", () => {
    profileMock.mockReturnValue({
      data: PROFILE,
      isFetching: false,
      refetch: vi.fn(),
    });
    overviewMock.mockReturnValue({
      data: {
        available: false,
        activationAllowed: false,
        latest: null,
        runs: [],
        notes: [],
      },
      isLoading: false,
      isError: false,
      isFetching: false,
      refetch: vi.fn(),
    });
    ledgerMock.mockReturnValue({
      data: null,
      isLoading: false,
      isError: false,
    });
    recomputeMock.mockReturnValue({
      isPending: false,
      isSuccess: false,
      isError: true,
      error: { status: 409, message: "no_declared_universe" },
      mutate: vi.fn(),
    });

    render(<StrategyVerificationPanel />);

    expect(
      screen.getByTestId("verification-recompute-error").textContent,
    ).toContain("no_declared_universe");
  });
});
