/**
 * AUTO UI REFACTOR 4.0 (P2) — Ficha universal de operación (read-model puro).
 *
 * Una sola ficha para cualquier operación (AUTO/MANUAL/SEMI): `QUÉ SE DECIDIÓ` · `QUÉ SE HIZO`
 * · `QUÉ CAMBIÓ` · `PRECIO` · `DINERO` · `ESTADO`, en el mismo orden. Reutiliza la tarjeta
 * canónica (`buildAutoOperationCard`); no re-deriva cifras ni salta peldaños.
 *
 * Invariantes:
 * - **No re-derivar.** Copia las ranuras ya producidas.
 * - **`UNKNOWN ≠ 0`.** Un campo sin medición se declara «Sin dato todavía».
 * - **Un peldaño no marca el siguiente.** «Precio aplicado» no es «Materializada».
 *
 * @see docs/engineering/spec-auto-operacion-usuario-basico-2026-10-06.md §4 §5
 */

import {
  type AutoBasicCycle,
  readEntryQuantities,
} from "@/features/auto/auto-basic-home";
import { AUTO_HOME_NO_DATA_LABEL } from "@/features/auto/auto-home-summary";
import {
  buildAutoOperationCard,
  type AutoOperationCardAccount,
} from "@/features/auto/auto-operation-card";

export const AUTO_SHEET_MODE_LABEL = "AUTO · SIMULADO";

export type AutoOperationSheetBlockId =
  | "decided"
  | "did"
  | "changed"
  | "price"
  | "money"
  | "status";

export type AutoOperationSheetBlock = {
  id: AutoOperationSheetBlockId;
  label: string;
  value: string;
  detail: string | null;
};

export type AutoOperationSheetV1 = {
  cycleId: string;
  symbol: string;
  modeLabel: string;
  headline: string;
  blocks: AutoOperationSheetBlock[];
};

const BLOCK_LABELS: readonly {
  id: AutoOperationSheetBlockId;
  label: string;
}[] = [
  { id: "decided", label: "Qué se decidió" },
  { id: "did", label: "Qué se hizo" },
  { id: "changed", label: "Qué cambió" },
  { id: "price", label: "Precio" },
  { id: "money", label: "Dinero" },
  { id: "status", label: "Estado" },
];

/** Claves candidatas de precio, por etapa (fail-closed: medición `COMPLETE`). */
const PRICE_KEYS_BY_STEP: Record<string, readonly string[]> = {
  FILL: ["appliedPrice", "fillPrice", "price", "entryPrice"],
  ORDER: ["entryPrice", "price", "limitPrice"],
};

function readNumericFact(
  cycle: AutoBasicCycle,
  stepId: string,
  keys: readonly string[],
): number | null {
  const step = (cycle.steps ?? []).find((item) => item.id === stepId);
  if (step?.state !== "reached") return null;
  for (const fact of step.facts ?? []) {
    if (!keys.includes(fact.key)) continue;
    if ((fact.measurement ?? "UNKNOWN") !== "COMPLETE") continue;
    const value = fact.value;
    if (typeof value === "number" && Number.isFinite(value)) return value;
    if (value && typeof value === "object") {
      const row = value as Record<string, unknown>;
      for (const key of keys) {
        const candidate = row[key];
        if (typeof candidate === "number" && Number.isFinite(candidate)) {
          return candidate;
        }
      }
    }
  }
  return null;
}

function priceBlock(cycle: AutoBasicCycle): {
  value: string;
  detail: string | null;
} {
  const fill = readNumericFact(cycle, "FILL", PRICE_KEYS_BY_STEP.FILL ?? []);
  if (fill != null)
    return { value: fill.toFixed(2), detail: "Precio aplicado" };
  const order = readNumericFact(cycle, "ORDER", PRICE_KEYS_BY_STEP.ORDER ?? []);
  if (order != null)
    return { value: order.toFixed(2), detail: "Precio de la orden" };
  const { requested } = readEntryQuantities(cycle);
  if (requested != null) {
    return {
      value: AUTO_HOME_NO_DATA_LABEL,
      detail: `${requested} solicitadas`,
    };
  }
  return { value: AUTO_HOME_NO_DATA_LABEL, detail: null };
}

export function buildAutoOperationSheet(
  cycle: AutoBasicCycle,
  account: AutoOperationCardAccount | null = null,
): AutoOperationSheetV1 {
  const card = buildAutoOperationCard(cycle, account);
  const slot = (id: string) => card.slots.find((s) => s.id === id);
  const decision = slot("decision");
  const execution = slot("execution");
  const simulation = slot("simulation");
  const position = slot("position");
  const money = slot("money");

  const changedParts = [simulation?.state, position?.state].filter(
    (part): part is string => part != null && part !== AUTO_HOME_NO_DATA_LABEL,
  );

  const blocks: Record<
    AutoOperationSheetBlockId,
    { value: string; detail: string | null }
  > = {
    decided: {
      value: decision?.state ?? AUTO_HOME_NO_DATA_LABEL,
      detail: decision?.detail ?? null,
    },
    did: {
      value: execution?.state ?? AUTO_HOME_NO_DATA_LABEL,
      detail: execution?.detail ?? null,
    },
    changed: {
      value:
        changedParts.length > 0
          ? changedParts.join(" · ")
          : AUTO_HOME_NO_DATA_LABEL,
      detail: null,
    },
    price: priceBlock(cycle),
    money: {
      value: money?.state ?? AUTO_HOME_NO_DATA_LABEL,
      detail: money?.detail ?? null,
    },
    status: { value: card.headline, detail: null },
  };

  return {
    cycleId: card.cycleId,
    symbol: card.symbol,
    modeLabel: AUTO_SHEET_MODE_LABEL,
    headline: card.headline,
    blocks: BLOCK_LABELS.map((b) => ({
      id: b.id,
      label: b.label,
      value: blocks[b.id].value,
      detail: blocks[b.id].detail,
    })),
  };
}
