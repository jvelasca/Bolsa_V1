/**
 * Layouts nombrados V1.31.2 — presets de dock Mercado (no nuevas regiones shell).
 * SIMPLE | TRADER | ANALISTA.
 */

export type NamedLayoutId = "simple" | "trader" | "analista";

export const NAMED_LAYOUT_DEFAULT: NamedLayoutId = "trader";

export const NAMED_LAYOUT_LABELS: Record<NamedLayoutId, string> = {
  simple: "Simple",
  trader: "Trader",
  analista: "Analista",
};

export function isNamedLayoutId(value: unknown): value is NamedLayoutId {
  return value === "simple" || value === "trader" || value === "analista";
}

/** Snapshot de visibilidad de docks (maximize siempre off al aplicar). */
export type NamedLayoutDockSnapshot = {
  listsOpen: boolean;
  chartsOpen: boolean;
  operationsOpen: boolean;
  operativaOpen: boolean;
};

export function namedLayoutDockSnapshot(
  id: NamedLayoutId,
): NamedLayoutDockSnapshot {
  switch (id) {
    case "simple":
      return {
        listsOpen: false,
        chartsOpen: true,
        operationsOpen: false,
        operativaOpen: true,
      };
    case "analista":
      return {
        listsOpen: true,
        chartsOpen: true,
        operationsOpen: false,
        operativaOpen: true,
      };
    case "trader":
    default:
      return {
        listsOpen: true,
        chartsOpen: true,
        operationsOpen: true,
        operativaOpen: true,
      };
  }
}
