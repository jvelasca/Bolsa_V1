/**
 * AUTO UI REFACTOR 4.0 (P1) — Centro de actividad (contrato del read-model).
 */

import { describe, expect, it } from "vitest";
import {
  AUTO_ACTIVITY_EMPTY_LABEL,
  AUTO_ACTIVITY_TICK_LABEL,
  activityClockLabel,
  buildAutoActivityFeed,
} from "@/features/auto/auto-activity-feed";

describe("buildAutoActivityFeed", () => {
  it("fusiona los pasos alcanzados y el reloj de decisión en una línea descendente", () => {
    const feed = buildAutoActivityFeed({
      header: { lastDecisionAt: "2026-10-06T09:42:00Z" },
      cycles: [
        {
          cycleId: "cyc-1",
          instrumentId: "AAPL",
          steps: [
            { id: "SIGNAL", state: "reached", at: "2026-10-06T09:00:00Z" },
            { id: "ORDER", state: "reached", at: "2026-10-06T09:10:00Z" },
            { id: "FILL", state: "pending", at: "2026-10-06T09:20:00Z" },
          ],
        },
      ],
    });
    expect(feed.hasEntries).toBe(true);
    expect(feed.entries.map((e) => e.atLabel)).toEqual([
      "09:42",
      "09:10",
      "09:00",
    ]);
    expect(feed.entries.map((e) => e.label)).toEqual([
      AUTO_ACTIVITY_TICK_LABEL,
      "Orden anotada",
      "Aviso de entrada",
    ]);
  });

  it("un paso no alcanzado no produce fila", () => {
    const feed = buildAutoActivityFeed({
      header: { lastDecisionAt: null },
      cycles: [
        {
          cycleId: "cyc-1",
          instrumentId: "AAPL",
          steps: [{ id: "FILL", state: "pending", at: "2026-10-06T09:20:00Z" }],
        },
      ],
    });
    expect(feed.hasEntries).toBe(false);
    expect(feed.emptyLabel).toBe(AUTO_ACTIVITY_EMPTY_LABEL);
  });

  it("un paso alcanzado sin sello no inventa una hora", () => {
    const feed = buildAutoActivityFeed({
      header: { lastDecisionAt: null },
      cycles: [
        {
          cycleId: "cyc-1",
          instrumentId: "AAPL",
          steps: [{ id: "ORDER", state: "reached", at: null }],
        },
      ],
    });
    expect(feed.hasEntries).toBe(false);
  });

  it("copia el símbolo y el cycleId como deep-link, sin exponer cycleId como texto", () => {
    const feed = buildAutoActivityFeed({
      header: { lastDecisionAt: null },
      cycles: [
        {
          cycleId: "cyc-1",
          instrumentId: "AAPL",
          steps: [
            { id: "ORDER", state: "reached", at: "2026-10-06T09:10:00Z" },
          ],
        },
      ],
    });
    const entry = feed.entries[0]!;
    expect(entry.symbol).toBe("AAPL");
    expect(entry.cycleId).toBe("cyc-1");
    expect(entry.label).not.toContain("cyc-1");
  });

  it("respeta el límite", () => {
    const feed = buildAutoActivityFeed(
      {
        header: { lastDecisionAt: "2026-10-06T09:42:00Z" },
        cycles: [
          {
            cycleId: "cyc-1",
            instrumentId: "AAPL",
            steps: [
              { id: "SIGNAL", state: "reached", at: "2026-10-06T09:00:00Z" },
              { id: "ORDER", state: "reached", at: "2026-10-06T09:10:00Z" },
            ],
          },
        ],
      },
      { limit: 1 },
    );
    expect(feed.entries).toHaveLength(1);
  });

  it("activityClockLabel es determinista", () => {
    expect(activityClockLabel("2026-10-06T09:42:00Z")).toBe("09:42");
    expect(activityClockLabel(null)).toBe("Sin dato todavía");
  });
});
