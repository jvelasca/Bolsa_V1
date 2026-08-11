import { describe, expect, it } from "vitest";

import { drawingMarkerToSignalEventV1 } from "@bolsa/shared";

describe("drawingMarkerToSignalEventV1", () => {
  it("maps up/down crosses to entry_long/exit", () => {
    const up = drawingMarkerToSignalEventV1(
      {
        id: "m-up",
        drawingId: "d1",
        timestamp: "2024-01-10",
        price: 105.5,
        level: 105,
        direction: "up",
        drawingType: "hline",
      },
      {
        instrumentId: "inst-1",
        strategyDefinitionId: "strat-1",
        strategyVersion: 2,
        barIndex: 9,
      },
    );

    expect(up.kind).toBe("entry_long");
    expect(up.barIndex).toBe(9);
    expect(up.id).toBe("sig:draw:m-up");

    const down = drawingMarkerToSignalEventV1(
      {
        id: "m-down",
        drawingId: "d1",
        timestamp: "2024-01-11",
        price: 104,
        level: 105,
        direction: "down",
        drawingType: "hline",
      },
      {
        instrumentId: "inst-1",
        strategyDefinitionId: "strat-1",
        strategyVersion: 2,
        barIndex: 10,
      },
    );

    expect(down.kind).toBe("exit");
  });
});
