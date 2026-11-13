/**
 * Proyección pura de los niveles CALCULADOS (S2) al gráfico.
 *
 * Solo `detectado` produce línea. `no_fiable`, `roto`, `en_precio` y
 * `no_disponible` se declaran en el panel de lectura y NO se dibujan: pintarlos
 * sería convertir una duda en una línea que parece estructura.
 *
 * El estilo es deliberadamente distinto del preset manual (`chart-sr-presets`):
 * discontinuo, etiqueta `S·calc` / `R·calc` y colores propios. Un nivel calculado
 * nunca debe leerse como una línea que el usuario dibujó.
 *
 * @see docs/engineering/metodologia-soportes-resistencias-tendencia-2026-11-12.md
 */

import {
  formatLevel,
  marketLevelIsDrawable,
  marketLevelKindShortLabel,
  type MarketStructureResultV1,
  type MarketLevelV1,
} from "@bolsa/shared";

export type MarketStructureChartLevelStyle = "dashed";

export type MarketStructureChartLevel = {
  /** ID estable para reconciliar la priceLine sin recrearla. */
  id: string;
  kind: MarketLevelV1["kind"];
  price: number;
  title: string;
  color: string;
  style: MarketStructureChartLevelStyle;
  width: 1;
  /** Nivel del plan operativo que coincide (informativo, no autoriza nada). */
  collidesWith: string | null;
};

export const MARKET_STRUCTURE_LEVEL_ID_PREFIX = "market-structure-level";

/** Distintos del verde/rojo de los presets manuales a propósito. */
const LEVEL_COLORS = {
  support: "#0d9488",
  resistance: "#9333ea",
} as const;

export type MarketStructurePlanPrice = {
  price: number;
  title: string;
};

function collisionFor(
  price: number,
  atrRef: number | null,
  toleranceAtrMultiple: number,
  planPrices: readonly MarketStructurePlanPrice[],
): string | null {
  if (atrRef == null || !Number.isFinite(atrRef) || planPrices.length === 0) {
    return null;
  }
  const tolerance = atrRef * toleranceAtrMultiple;
  const match = planPrices.find(
    (item) =>
      Number.isFinite(item.price) && Math.abs(item.price - price) <= tolerance,
  );
  return match ? match.title : null;
}

/**
 * Niveles a dibujar. Vacío cuando no hay medición (`insufficient_history` /
 * `no_disponible`) o cuando ningún nivel es `detectado`.
 */
export function buildMarketStructureChartLevels(input: {
  result: MarketStructureResultV1 | null | undefined;
  /** Entrada / stop / T1 / T2 del plan operativo, para declarar coincidencias. */
  planLevels?: readonly MarketStructurePlanPrice[];
}): MarketStructureChartLevel[] {
  const result = input.result;
  if (!result || result.status !== "ok") return [];
  const planLevels = input.planLevels ?? [];
  const toleranceMultiple = result.params.inPriceAtrMultiple;

  const levels: MarketStructureChartLevel[] = [];
  const push = (level: MarketLevelV1, index: number) => {
    if (!marketLevelIsDrawable(level)) return;
    const collidesWith = collisionFor(
      level.price,
      result.atrRef,
      toleranceMultiple,
      planLevels,
    );
    const base = `${marketLevelKindShortLabel(level.kind)} ${formatLevel(level.price)}`;
    levels.push({
      id: `${MARKET_STRUCTURE_LEVEL_ID_PREFIX}:${level.kind}:${index}`,
      kind: level.kind,
      price: level.price,
      title: collidesWith ? `${base} · coincide con ${collidesWith}` : base,
      color: LEVEL_COLORS[level.kind],
      style: "dashed",
      width: 1,
      collidesWith,
    });
  };
  result.supports.forEach(push);
  result.resistances.forEach(push);
  return levels;
}

/** Huella de las líneas para reconciliar sin recrearlas en cada render. */
export function marketStructureChartLevelsSignature(
  levels: readonly MarketStructureChartLevel[],
): string {
  return levels
    .map((level) => `${level.id}@${level.price}@${level.title}@${level.style}`)
    .join("|");
}

/**
 * Resumen para la leyenda. Declara el hueco en vez de mostrar «0 niveles» como
 * si se hubiera medido y no hubiera nada.
 */
export function describeMarketStructureLevels(
  result: MarketStructureResultV1 | null | undefined,
): {
  measured: boolean;
  supports: number;
  resistances: number;
  detail: string;
} {
  if (!result || result.status !== "ok") {
    return {
      measured: false,
      supports: 0,
      resistances: 0,
      detail:
        result?.status === "insufficient_history"
          ? "Histórico insuficiente"
          : "Sin niveles calculados",
    };
  }
  const supports = result.supports.filter(marketLevelIsDrawable).length;
  const resistances = result.resistances.filter(marketLevelIsDrawable).length;
  if (supports + resistances === 0) {
    return {
      measured: true,
      supports,
      resistances,
      detail: "Sin niveles fiables en la ventana",
    };
  }
  return {
    measured: true,
    supports,
    resistances,
    detail: `${supports} soporte${supports === 1 ? "" : "s"} · ${resistances} resistencia${resistances === 1 ? "" : "s"}`,
  };
}
