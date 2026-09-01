/**
 * V1.47 — OperationalContext / nextAction / freshness classification.
 */

import { describe, expect, it } from "vitest";
import {
  classifyMarketData,
  resolveDecisionAction,
  resolveExecutedAction,
  resolvePaperDeskNextAction,
  resolvePositionOperatingState,
  sessionIsOpen,
} from "./operational-context.js";

describe("operational-context", () => {
  it("classifies missing / stale / fresh", () => {
    expect(
      classifyMarketData({
        lastPrice: null,
        barDate: null,
        expectedIsoDate: "2026-08-31",
      }),
    ).toBe("MISSING");
    expect(
      classifyMarketData({
        lastPrice: 100,
        barDate: "2026-08-20",
        expectedIsoDate: "2026-08-31",
      }),
    ).toBe("STALE");
    expect(
      classifyMarketData({
        lastPrice: 100,
        barDate: "2026-08-31",
        expectedIsoDate: "2026-08-31",
      }),
    ).toBe("FRESH");
    expect(
      classifyMarketData({
        lastPrice: -1,
        barDate: "2026-08-31",
        expectedIsoDate: "2026-08-31",
      }),
    ).toBe("INVALID");
  });

  it("maps nextAction from row status", () => {
    expect(
      resolvePaperDeskNextAction({ status: "held", reason: "data_stale" }),
    ).toBe("REVISAR_DATOS_NO_FRESCOS");
    expect(
      resolvePaperDeskNextAction({
        status: "held",
        reason: "queue_next_session",
        session: "CLOSED",
      }),
    ).toBe("ESPERAR_APERTURA");
    expect(resolvePaperDeskNextAction({ status: "protected" })).toBe("MONITOR");
    expect(
      resolvePaperDeskNextAction({ status: "protected", reason: "dry_run" }),
    ).toBe("SUBIR_STOP");
    expect(resolvePaperDeskNextAction({ status: "denied" })).toBe("BLOQUEADO");
    expect(sessionIsOpen("OPEN")).toBe(true);
    expect(sessionIsOpen("POST")).toBe(false);
  });

  it("splits decision / executed / nextAction", () => {
    expect(
      resolveExecutedAction({ status: "protected", reason: "dry_run" }),
    ).toBe("DRY_RUN");
    expect(resolveDecisionAction("TRAIL")).toBe("TRAIL");
    expect(
      resolvePositionOperatingState({
        remainingQuantity: 7,
        quantity: 10,
      }),
    ).toBe("PARTIALLY_REDUCED");
  });

  it("V1.57: drift → RECONCILIATION_DRIFT; unavailable → RECONCILIATION_ERROR", () => {
    expect(
      resolvePositionOperatingState({
        positionStatus: "PROTECTED",
        hasProtectRevision: true,
        reconStatus: "drift",
      }),
    ).toBe("RECONCILIATION_DRIFT");
    expect(
      resolvePositionOperatingState({
        positionStatus: "PROTECTED",
        hasProtectRevision: true,
        reconStatus: "unavailable",
      }),
    ).toBe("RECONCILIATION_ERROR");
    expect(
      resolvePositionOperatingState({
        positionStatus: "PROTECTED",
        hasProtectRevision: true,
        reconStatus: "clean",
      }),
    ).toBe("PROTECTED");
  });
});
