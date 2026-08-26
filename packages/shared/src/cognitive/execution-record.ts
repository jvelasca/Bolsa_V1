/**
 * ExecutionRecord — resultado de un intento de envío (ADR-034 OI-3).
 * UNKNOWN ≠ ERROR. Excepción tras intentar enviar ≠ no-ejecutado.
 * ≠ ExecutionPlan (F4) ≠ ExecuteTrade ≠ broker.
 */

export type ExecutionOutcomeV1 =
  | "not_executed"
  | "executed"
  | "error"
  | "unknown";

export type ExecutionRecordV1 = {
  outcome: ExecutionOutcomeV1;
  reason: string | null;
  transactionId: string | null;
  sendAttempted: boolean;
};

export const EXECUTION_RECORD_KEY = "executionRecord";

export type BuildExecutionRecordInputV1 = {
  filled?: boolean;
  sendAttempted?: boolean;
  transactionId?: string | null;
  exception?: string | null;
  notExecutedReason?: string | null;
};

function nonEmpty(value: string | null | undefined): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

/**
 * Kernel: filled → executed; send without fill → unknown;
 * pre-send exception → error; else not_executed.
 */
export function buildExecutionRecord(
  input: BuildExecutionRecordInputV1 = {},
): ExecutionRecordV1 {
  const transactionId = nonEmpty(input.transactionId ?? null);
  const exception = nonEmpty(input.exception ?? null);
  const notExecutedReason = nonEmpty(input.notExecutedReason ?? null);

  if (input.filled === true) {
    return {
      outcome: "executed",
      reason: null,
      transactionId,
      sendAttempted: true,
    };
  }
  if (input.sendAttempted === true) {
    return {
      outcome: "unknown",
      reason: exception ?? "execute_exception",
      transactionId: null,
      sendAttempted: true,
    };
  }
  if (exception) {
    return {
      outcome: "error",
      reason: exception,
      transactionId: null,
      sendAttempted: false,
    };
  }
  return {
    outcome: "not_executed",
    reason: notExecutedReason,
    transactionId: null,
    sendAttempted: false,
  };
}

/** Copy de mesa: unknown nunca se lee como «no se ejecutó». */
export function executionOutcomeCopy(outcome: ExecutionOutcomeV1): string {
  switch (outcome) {
    case "executed":
      return "Ejecutado";
    case "not_executed":
      return "No se envió";
    case "error":
      return "Error antes de enviar (no ejecutado)";
    case "unknown":
      return "Resultado desconocido — no asumir que no se ejecutó";
  }
}
