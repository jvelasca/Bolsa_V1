/**
 * Fusión servidor ↔ backup local: la MEMBRESÍA de pestañas la dicta el documento
 * más reciente. Nunca se añaden pestañas del documento antiguo.
 *
 * Regresión: Visualizados volvía a mostrar 200+ instrumentos tras recargar porque
 * el backup podado (1 pestaña) se unía al documento viejo del servidor (214).
 *
 * @see docs/WORKSPACE_PERSISTENCE.md §2b
 */
import { describe, expect, it } from "vitest";
import {
  DEFAULT_CHART_CONFIG,
  type ChartDrawing,
  type ChartTabState,
  type WorkspaceDocument,
} from "@bolsa/shared";
import {
  mergeWorkspaceChartState,
  syncSnapshotsFromCharts,
} from "@/lib/chart-list-snapshot";
import { DEFAULT_WORKSPACE } from "@/stores/workspace-store-core";

function tab(
  id: string,
  instrumentId: string,
  extra: Partial<ChartTabState> = {},
): ChartTabState {
  return {
    id,
    instrumentId,
    label: instrumentId.toUpperCase(),
    timeframe: "1D",
    seriesType: "candles",
    chart: DEFAULT_CHART_CONFIG,
    indicatorInstances: [],
    drawings: [],
    ...extra,
  } as ChartTabState;
}

function doc(
  updatedAt: string,
  charts: ChartTabState[],
  extra: Partial<WorkspaceDocument> = {},
): WorkspaceDocument {
  return {
    ...DEFAULT_WORKSPACE,
    updatedAt,
    charts,
    activeChartId: charts.at(-1)?.id ?? null,
    ...extra,
  };
}

function ids(charts: ChartTabState[]): string[] {
  return charts.map((item) => item.instrumentId);
}

describe("mergeWorkspaceChartState — membresía newest-wins", () => {
  it("el backup podado (1) gana sobre el servidor viejo con 214 pestañas", () => {
    const oldServer = doc(
      "2026-11-01T10:00:00.000Z",
      Array.from({ length: 214 }, (_, index) =>
        tab(`s${index}`, `inst-${index}`),
      ),
    );
    const freshBackup = doc("2026-11-02T10:00:00.000Z", [tab("b1", "inst-7")]);

    const merged = mergeWorkspaceChartState(freshBackup, oldServer);

    expect(merged.charts).toHaveLength(1);
    expect(ids(merged.charts)).toEqual(["inst-7"]);
    expect(merged.activeChartId).toBe("b1");
  });

  it("el servidor más reciente con 3 pestañas no hereda las 10 del backup", () => {
    const backup = doc(
      "2026-11-01T10:00:00.000Z",
      Array.from({ length: 10 }, (_, index) =>
        tab(`b${index}`, `inst-${index}`),
      ),
    );
    const server = doc("2026-11-02T10:00:00.000Z", [
      tab("s1", "inst-1"),
      tab("s2", "inst-2"),
      tab("s3", "inst-3"),
    ]);

    const merged = mergeWorkspaceChartState(server, backup);

    expect(ids(merged.charts)).toEqual(["inst-1", "inst-2", "inst-3"]);
  });

  it("una pestaña presente en ambos documentos conserva los dibujos del más reciente", () => {
    const drawing = { id: "d1", type: "hline", price: 100 } as ChartDrawing;
    const newer = doc("2026-11-02T10:00:00.000Z", [
      tab("n1", "meta", { drawings: [drawing] }),
    ]);
    const older = doc("2026-11-01T10:00:00.000Z", [
      tab("o1", "meta", { drawings: [] }),
    ]);

    const merged = mergeWorkspaceChartState(newer, older);

    expect(merged.charts).toHaveLength(1);
    expect(merged.charts[0]?.instrumentId).toBe("meta");
    // Se fusiona el estado interno de la pestaña compartida, pero el borrado de
    // dibujos del documento autoritativo (el más reciente) no se deshace.
    expect(merged.charts[0]?.drawings.map((item) => item.id)).toEqual(["d1"]);
  });

  it("no duplica instrumentos y recalcula activeChartId si el activo desaparece", () => {
    const newer = doc(
      "2026-11-02T10:00:00.000Z",
      [tab("n1", "aapl"), tab("n2", "msft")],
      { activeChartId: "cerrada" },
    );
    const older = doc("2026-11-01T10:00:00.000Z", [
      tab("o1", "aapl"),
      tab("o2", "aapl"),
      tab("o3", "tsla"),
    ]);

    const merged = mergeWorkspaceChartState(newer, older);

    expect(ids(merged.charts)).toEqual(["aapl", "msft"]);
    expect(merged.charts.some((item) => item.id === "cerrada")).toBe(false);
    expect(merged.charts.some((item) => item.id === merged.activeChartId)).toBe(
      true,
    );
  });

  it("los snapshots huérfanos de instrumentos cerrados se descartan", () => {
    const newer = doc("2026-11-02T10:00:00.000Z", [
      tab("n1", "aapl", { sourceListId: "estudio" }),
    ]);
    const older = doc(
      "2026-11-01T10:00:00.000Z",
      [
        tab("o1", "aapl", { sourceListId: "estudio" }),
        tab("o2", "tsla", { sourceListId: "estudio" }),
      ],
      {
        chartStateByListInstrument: {
          "estudio::aapl": { instrumentId: "aapl" } as never,
          "estudio::tsla": { instrumentId: "tsla" } as never,
        },
      },
    );

    const merged = mergeWorkspaceChartState(newer, older);

    expect(Object.keys(merged.chartStateByListInstrument ?? {})).toEqual([
      "estudio::aapl",
    ]);
  });

  it("un chartListContext de un instrumento cerrado no sobrevive a la fusión", () => {
    // Regresión: `newerDoc.chartListContext ?? olderDoc.chartListContext` revivía el
    // contexto del documento antiguo cuando el nuevo ya no tenía pestaña abierta.
    const newer = doc("2026-11-02T10:00:00.000Z", [
      tab("n1", "aapl", { sourceListId: "estudio" }),
    ]);
    const older = doc(
      "2026-11-01T10:00:00.000Z",
      [tab("o1", "aapl", { sourceListId: "estudio" }), tab("o2", "tsla")],
      {
        chartListContext: { listId: "estudio", instrumentId: "tsla" },
      },
    );

    const merged = mergeWorkspaceChartState(newer, older);

    expect(merged.chartListContext ?? null).toBeNull();
  });
});

describe("syncSnapshotsFromCharts — el snapshot sigue al estado vivo", () => {
  function snapshotFor(
    instrumentId: string,
    overrides: Record<string, unknown> = {},
  ): Record<string, unknown> {
    return {
      timeframe: "1D",
      seriesType: "candles",
      chart: DEFAULT_CHART_CONFIG,
      indicatorInstances: [],
      drawings: [],
      openDrawingEditorId: null,
      activeIndicatorTemplateId: null,
      ...overrides,
    };
  }

  function indicator(id: string, period: number) {
    return {
      id,
      definitionId: "rsi",
      parameters: { period },
      visible: true,
    } as never;
  }

  it("propaga cambios de parámetros aunque el número de indicadores no cambie", () => {
    const workspace = doc(
      "2026-11-02T10:00:00.000Z",
      [tab("n1", "aapl", { indicatorInstances: [indicator("i1", 50)] })],
      {
        chartStateByListInstrument: {
          "ibex35::aapl": snapshotFor("aapl", {
            indicatorInstances: [indicator("i1", 14)],
          }) as never,
        },
      },
    );

    const synced = syncSnapshotsFromCharts(workspace);
    const snapshot = synced.chartStateByListInstrument!["ibex35::aapl"]!;

    expect(
      (snapshot.indicatorInstances[0]!.parameters as { period: number }).period,
    ).toBe(50);
  });

  it("propaga cambios de geometría aunque el número de dibujos no cambie", () => {
    const drawing = (price: number) =>
      ({ id: "d1", type: "hline", price }) as never;
    const workspace = doc(
      "2026-11-02T10:00:00.000Z",
      [tab("n1", "aapl", { drawings: [drawing(120)] })],
      {
        chartStateByListInstrument: {
          "ibex35::aapl": snapshotFor("aapl", {
            drawings: [drawing(100)],
          }) as never,
        },
      },
    );

    const synced = syncSnapshotsFromCharts(workspace);
    const snapshot = synced.chartStateByListInstrument!["ibex35::aapl"]!;

    expect((snapshot.drawings[0] as unknown as { price: number }).price).toBe(
      120,
    );
  });

  it("no reescribe el workspace cuando el snapshot ya coincide", () => {
    const workspace = doc("2026-11-02T10:00:00.000Z", [tab("n1", "aapl")], {
      chartStateByListInstrument: {
        "ibex35::aapl": snapshotFor("aapl") as never,
      },
    });

    expect(syncSnapshotsFromCharts(workspace)).toBe(workspace);
  });
});
