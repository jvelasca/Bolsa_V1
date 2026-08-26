/**
 * ExecutionRecord OI-3 — UNKNOWN ≠ ERROR (ADR-034).
 */

import { describe, expect, it } from "vitest";
import {
  buildExecutionRecord,
  executionOutcomeCopy,
  type ExecutionRecordV1,
} from "./cognitive/execution-record.js";

describe("OI-3 buildExecutionRecord", () => {
  it("filled → executed even if exception is also present (OI-1)", () => {
    const rec = buildExecutionRecord({
      filled: true,
      sendAttempted: true,
      transactionId: "tx-1",
      exception: "persist boom",
    });
    expect(rec.outcome).toBe("executed");
    expect(rec.transactionId).toBe("tx-1");
    expect(rec.sendAttempted).toBe(true);
    expect(rec.reason).toBeNull();
  });

  it("send attempted without fill → unknown, never error or not_executed", () => {
    const rec = buildExecutionRecord({
      sendAttempted: true,
      exception: "ledger timeout",
    });
    expect(rec.outcome).toBe("unknown");
    expect(rec.reason).toBe("ledger timeout");
    expect(rec.sendAttempted).toBe(true);
    expect(rec.transactionId).toBeNull();
    expect(rec.outcome).not.toBe("error");
    expect(rec.outcome).not.toBe("not_executed");
  });

  it("send attempted with silence (no fill, no exception) → unknown", () => {
    const rec = buildExecutionRecord({ sendAttempted: true });
    expect(rec.outcome).toBe("unknown");
    expect(rec.reason).toBe("execute_exception");
  });

  it("pre-send exception → error (we know it was not sent)", () => {
    const rec = buildExecutionRecord({ exception: "journal boom" });
    expect(rec.outcome).toBe("error");
    expect(rec.sendAttempted).toBe(false);
  });

  it("gate/skip before send → not_executed", () => {
    const rec = buildExecutionRecord({ notExecutedReason: "risk_signature" });
    expect(rec.outcome).toBe("not_executed");
    expect(rec.reason).toBe("risk_signature");
    expect(rec.sendAttempted).toBe(false);
  });
});

describe("OI-3 executionOutcomeCopy", () => {
  it("unknown copy does not say it was not executed", () => {
    expect(executionOutcomeCopy("unknown")).toMatch(/desconocido/i);
    expect(executionOutcomeCopy("unknown")).toMatch(/no asumir/i);
    expect(executionOutcomeCopy("error")).toMatch(/no ejecutado/i);
    expect(executionOutcomeCopy("not_executed")).toMatch(/No se envió/);
    const executed: ExecutionRecordV1 = buildExecutionRecord({ filled: true });
    expect(executionOutcomeCopy(executed.outcome)).toBe("Ejecutado");
  });
});
