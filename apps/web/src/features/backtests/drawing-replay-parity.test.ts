import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import type { ChartDrawing, OhlcvBarDto } from "@bolsa/shared";
import { evaluateDrawingReplay } from "@bolsa/shared";

const fixtureDir = join(
  dirname(fileURLToPath(import.meta.url)),
  "../../../../../packages/py/analytics/tests/fixtures",
);
const golden = JSON.parse(
  readFileSync(join(fixtureDir, "drawing_replay_golden.json"), "utf8"),
) as {
  bars: OhlcvBarDto[];
  drawings: ChartDrawing[];
  expectedMarkers: Array<{
    id: string;
    drawingId: string;
    timestamp: string;
    price: number;
    level: number;
    direction: "up" | "down";
    drawingType: ChartDrawing["type"];
  }>;
};

describe("drawing replay golden parity (TS vs Python fixture)", () => {
  it("matches expected backtest_marker events", () => {
    const markers = evaluateDrawingReplay(golden.bars, golden.drawings);
    expect(markers).toHaveLength(golden.expectedMarkers.length);
    for (let i = 0; i < markers.length; i += 1) {
      const marker = markers[i]!;
      const expected = golden.expectedMarkers[i]!;
      expect(marker.id).toBe(expected.id);
      expect(marker.drawingId).toBe(expected.drawingId);
      expect(marker.timestamp).toBe(expected.timestamp);
      expect(marker.price).toBe(expected.price);
      expect(marker.level).toBe(expected.level);
      expect(marker.direction).toBe(expected.direction);
      expect(marker.drawingType).toBe(expected.drawingType);
    }
  });
});
