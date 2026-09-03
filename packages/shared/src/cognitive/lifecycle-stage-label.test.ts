/**
 * V1.90 — lifecycle stage label unit tests.
 */

import { describe, expect, it } from "vitest";
import {
  LIFECYCLE_STAGE_LABELS,
  lifecycleStageLabel,
} from "./lifecycle-stage-label.js";

describe("lifecycleStageLabel", () => {
  it("maps machine stages to operational copy", () => {
    expect(lifecycleStageLabel("t1_executed")).toBe("T1 ejecutado");
    expect(lifecycleStageLabel("trailing")).toBe("Protegiendo");
    expect(lifecycleStageLabel("exit_required")).toBe("Salida requerida");
    expect(lifecycleStageLabel("t2_ready")).toBe("T2 preparado");
    expect(lifecycleStageLabel("t2_executed")).toBe("T2 ejecutado");
    expect(lifecycleStageLabel("closed")).toBe("Cerrada");
    expect(lifecycleStageLabel("open")).toBe("Abierta");
  });

  it("hides candidate / empty", () => {
    expect(lifecycleStageLabel("candidate")).toBeNull();
    expect(lifecycleStageLabel(null)).toBeNull();
    expect(lifecycleStageLabel(undefined)).toBeNull();
  });

  it("exports full label table", () => {
    expect(Object.keys(LIFECYCLE_STAGE_LABELS).length).toBeGreaterThanOrEqual(
      8,
    );
  });
});
