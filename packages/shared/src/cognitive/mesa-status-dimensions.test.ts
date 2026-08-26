import { describe, expect, it } from "vitest";
import {
  mapMesaStatusDimensions,
  MESA_CANDIDATE_GROUP_LABEL,
} from "./mesa-status-dimensions.js";

describe("mapMesaStatusDimensions", () => {
  it("maps thesis, operational and position independently", () => {
    const dims = mapMesaStatusDimensions({
      study: {
        status: "in_progress",
        tradePlanStatus: "ARMED",
        hasOperationalPlan: true,
      },
      positionStatus: "OPEN",
      hasOpenPosition: true,
    });
    expect(dims.thesis).toBe("En desarrollo");
    expect(dims.operational).toBe("Preparada");
    expect(dims.position).toBe("Abierta");
  });

  it("shows sin posición when no open position", () => {
    const dims = mapMesaStatusDimensions({
      study: {
        status: "neutral",
        tradePlanStatus: "WATCH",
        hasOperationalPlan: false,
      },
      hasOpenPosition: false,
    });
    expect(dims.position).toBe("Sin posición");
    expect(dims.operational).toBe("Vigilar");
  });

  it("does not mutate status enum values", () => {
    expect(MESA_CANDIDATE_GROUP_LABEL.TRIGGERED).toBe("Listos");
    expect(MESA_CANDIDATE_GROUP_LABEL.ARMED).toBe("Preparados");
  });
});
