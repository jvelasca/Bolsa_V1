/**
 * Maximizar DECISIÓN (Operativa) — misma exclusión mutua que Listas /
 * Gráfico / Operaciones, y limpieza al cerrar / restaurar / aplicar preset.
 */

import { beforeEach, describe, expect, it } from "vitest";
import {
  DEFAULT_OPERATIVA_SECTION_HEIGHTS,
  useTradingLayoutStore,
} from "@/stores/trading-layout-store";

function reset() {
  useTradingLayoutStore.setState({
    listsOpen: true,
    chartsOpen: true,
    operationsOpen: true,
    operativaOpen: true,
    listsMaximized: false,
    chartsMaximized: false,
    operationsMaximized: false,
    operativaMaximized: false,
    namedLayoutId: "trader",
    operativaSections: {
      recomendacion: true,
      fundamental: false,
      tecnico: false,
      seguimientoDia: false,
      lab: false,
      mandato: false,
      evidencia: false,
      resultados: false,
      auto: false,
    },
    operativaSectionHeights: { ...DEFAULT_OPERATIVA_SECTION_HEIGHTS },
  });
}

beforeEach(() => {
  localStorage.clear();
  reset();
});

describe("trading-layout-store — maximizar DECISIÓN", () => {
  it("maximiza DECISIÓN y apaga los maximizados de las otras zonas", () => {
    useTradingLayoutStore.getState().maximizeLists();
    expect(useTradingLayoutStore.getState().listsMaximized).toBe(true);

    useTradingLayoutStore.getState().maximizeOperativa();

    const state = useTradingLayoutStore.getState();
    expect(state.operativaMaximized).toBe(true);
    expect(state.operativaOpen).toBe(true);
    expect(state.listsMaximized).toBe(false);
    expect(state.chartsMaximized).toBe(false);
    expect(state.operationsMaximized).toBe(false);
  });

  it("vuelve a dock normal al invocar maximizeOperativa de nuevo", () => {
    useTradingLayoutStore.getState().maximizeOperativa();
    useTradingLayoutStore.getState().maximizeOperativa();
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);
  });

  it("maximizar otra zona apaga DECISIÓN maximizada", () => {
    useTradingLayoutStore.getState().maximizeOperativa();
    useTradingLayoutStore.getState().maximizeOperations();
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);
    expect(useTradingLayoutStore.getState().operationsMaximized).toBe(true);

    useTradingLayoutStore.getState().maximizeOperativa();
    useTradingLayoutStore.getState().maximizeLists();
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);

    useTradingLayoutStore.getState().maximizeOperativa();
    useTradingLayoutStore.getState().maximizeCharts();
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);
  });

  it("cierra DECISIÓN maximizada al ocultar la zona y no la resucita al reabrir", () => {
    useTradingLayoutStore.getState().maximizeOperativa();
    useTradingLayoutStore.getState().toggleOperativa();

    expect(useTradingLayoutStore.getState().operativaOpen).toBe(false);
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);

    useTradingLayoutStore.getState().toggleOperativa();
    expect(useTradingLayoutStore.getState().operativaOpen).toBe(true);
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);
  });

  it("ensureOperativaOpen limpia el maximizado al reabrir una zona cerrada", () => {
    useTradingLayoutStore.setState({
      operativaOpen: false,
      operativaMaximized: true,
    });
    useTradingLayoutStore.getState().ensureOperativaOpen();
    expect(useTradingLayoutStore.getState().operativaOpen).toBe(true);
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);
  });

  it("restoreLayout y applyNamedLayout vuelven al dock normal", () => {
    useTradingLayoutStore.getState().maximizeOperativa();
    useTradingLayoutStore.getState().restoreLayout();
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);

    useTradingLayoutStore.getState().maximizeOperativa();
    useTradingLayoutStore.getState().applyNamedLayout("trader");
    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);
  });

  it("persiste el flag en la clave local del dock", () => {
    useTradingLayoutStore.getState().maximizeOperativa();
    const raw = localStorage.getItem("bolsa-trading-layout-v1");
    expect(raw).toBeTruthy();
    const persisted = JSON.parse(raw!) as { state?: Record<string, unknown> };
    expect(persisted.state?.operativaMaximized).toBe(true);
  });
});

describe("trading-layout-store — merge defensivo", () => {
  it("un estado guardado con DECISIÓN cerrada no la deja invisible", async () => {
    localStorage.setItem(
      "bolsa-trading-layout-v1",
      JSON.stringify({
        state: { operativaOpen: false, operativaMaximized: true },
        version: 0,
      }),
    );

    await useTradingLayoutStore.persist.rehydrate();

    expect(useTradingLayoutStore.getState().operativaMaximized).toBe(false);
  });
});

describe("trading-layout-store — bloques de DECISIÓN (V2.48)", () => {
  it("solo el grupo Recomendación del dock arranca abierto", () => {
    const state = useTradingLayoutStore.getState();
    expect(state.operativaSections).toEqual({
      recomendacion: true,
      fundamental: false,
      tecnico: false,
      seguimientoDia: false,
      lab: false,
      mandato: false,
      evidencia: false,
      resultados: false,
      auto: false,
    });
    expect(Object.keys(DEFAULT_OPERATIVA_SECTION_HEIGHTS)).toEqual([
      "recomendacion",
      "fundamental",
      "tecnico",
      "seguimientoDia",
      "lab",
      "mandato",
      "evidencia",
      "resultados",
      "auto",
    ]);
  });

  it("cada bloque recuerda estado y alto en la clave local del dock", () => {
    const { toggleOperativaSection, setOperativaSectionHeight } =
      useTradingLayoutStore.getState();
    toggleOperativaSection("mandato");
    setOperativaSectionHeight("mandato", 260);

    const state = useTradingLayoutStore.getState();
    expect(state.operativaSections.mandato).toBe(true);
    expect(state.operativaSections.lab).toBe(false);
    expect(state.operativaSectionHeights.mandato).toBe(260);

    const raw = localStorage.getItem("bolsa-trading-layout-v1");
    expect(raw).toBeTruthy();
    const persisted = JSON.parse(raw!) as {
      state?: {
        operativaSections?: Record<string, boolean>;
        operativaSectionHeights?: Record<string, number>;
      };
    };
    expect(persisted.state?.operativaSections?.mandato).toBe(true);
    expect(persisted.state?.operativaSectionHeights?.mandato).toBe(260);
  });

  it("un guardado con los ids viejos no rompe el rehidratado", async () => {
    localStorage.setItem(
      "bolsa-trading-layout-v1",
      JSON.stringify({
        state: {
          operativaSections: {
            recommendation: true,
            info: true,
            config: true,
          },
          operativaSectionHeights: {
            recommendation: 320,
            info: 200,
            config: 180,
          },
        },
        version: 0,
      }),
    );

    await useTradingLayoutStore.persist.rehydrate();

    const state = useTradingLayoutStore.getState();
    for (const id of [
      "recomendacion",
      "fundamental",
      "tecnico",
      "seguimientoDia",
      "lab",
      "mandato",
      "evidencia",
      "resultados",
      "auto",
    ] as const) {
      expect(state.operativaSections[id]).toBe(
        id === "recomendacion",
      );
      expect(state.operativaSectionHeights[id]).toBe(
        DEFAULT_OPERATIVA_SECTION_HEIGHTS[id],
      );
    }
  });

  it("un guardado sin los grupos del dock abre solo Recomendación", async () => {
    localStorage.setItem(
      "bolsa-trading-layout-v1",
      JSON.stringify({
        state: {
          operativaSections: {
            lab: true,
            mandato: true,
            evidencia: true,
            resultados: true,
            auto: true,
          },
        },
        version: 0,
      }),
    );

    await useTradingLayoutStore.persist.rehydrate();

    const state = useTradingLayoutStore.getState();
    expect(state.operativaSections.recomendacion).toBe(true);
    for (const id of [
      "fundamental",
      "tecnico",
      "seguimientoDia",
    ] as const) {
      expect(state.operativaSections[id]).toBe(false);
    }
    // El guardado previo del usuario no se pisa: sus bloques siguen abiertos.
    expect(state.operativaSections.lab).toBe(true);
  });
});
