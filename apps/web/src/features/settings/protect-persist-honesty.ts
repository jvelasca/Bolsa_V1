/**
 * PH-1 — honesty de Proteger en Confirm (persist None ≠ protect_applied).
 */

export type ConfirmTradeSlice =
  | {
      status?: string;
      reason?: string;
    }
  | null
  | undefined;

export type ConfirmPersistSlice =
  | {
      status?: string;
      reason?: string;
    }
  | undefined;

/** persist None/error ≠ protect_applied — no sacar de cola ni mandato. */
export function protectStopNotApplied(
  trade: ConfirmTradeSlice,
  positionPersist: ConfirmPersistSlice,
): boolean {
  if (trade?.status !== "skipped") return false;
  return (
    trade.reason === "stop_not_applied" ||
    trade.reason === "persist_error" ||
    positionPersist?.status === "skipped"
  );
}

export function protectPersistNote(
  positionPersist: ConfirmPersistSlice,
): string {
  if (positionPersist?.status === "error") {
    return ` · positionPersist=error (${positionPersist.reason ?? "?"})`;
  }
  if (positionPersist?.status === "skipped") {
    return ` · stop no aplicado (${positionPersist.reason ?? "stop_not_applied"})`;
  }
  return "";
}
