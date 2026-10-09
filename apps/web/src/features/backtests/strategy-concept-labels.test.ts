/**
 * P3 (Slice B) — el vocabulario separa SELECCIÓN y VALIDACIÓN y nunca filtra el enum crudo.
 */

import { describe, expect, it } from "vitest";
import { ABSENT_DATA_NOT_MEASURED } from "@/components/absent-data";
import {
  strategySelectionStatusLabel,
  strategyValidationLabel,
} from "@/features/backtests/strategy-concept-labels";

describe("strategy-concept-labels · selección vs validación", () => {
  it("localiza el estado de SELECCIÓN y nunca devuelve el enum crudo", () => {
    expect(strategySelectionStatusLabel("draft")).toBe("Borrador");
    expect(strategySelectionStatusLabel("semifinal")).toBe("Semifinal");
    expect(strategySelectionStatusLabel("active")).toBe("Activo");
    expect(strategySelectionStatusLabel(null)).toBe(ABSENT_DATA_NOT_MEASURED);
    expect(strategySelectionStatusLabel(undefined)).toBe(
      ABSENT_DATA_NOT_MEASURED,
    );
    for (const raw of ["draft", "semifinal", "active"] as const) {
      expect(strategySelectionStatusLabel(raw)).not.toBe(raw);
    }
  });

  it("localiza la VALIDACIÓN y nunca devuelve el enum crudo", () => {
    expect(strategyValidationLabel("lab_validated")).toBe("Lab OOS");
    expect(strategyValidationLabel("in_sample_only")).toBe("solo in-sample");
    expect(strategyValidationLabel(null)).toBe(ABSENT_DATA_NOT_MEASURED);
    expect(strategyValidationLabel(undefined)).toBe(ABSENT_DATA_NOT_MEASURED);
    for (const raw of ["lab_validated", "in_sample_only"] as const) {
      expect(strategyValidationLabel(raw)).not.toBe(raw);
    }
  });
});
