/** Persistent favorites + floating cursor panel position for backtest HUD. */

export const BACKTEST_HUD_PREFS_KEY = "bolsa-backtest-hud-prefs-v1";

export type BacktestGlobalFieldId =
  | "identity"
  | "result"
  | "cashFlow"
  | "winLossDonut"
  | "moneyDonut"
  | "drawdown"
  | "vsBuyHold"
  | "opsSummary"
  | "closedNet";

export type BacktestTemporalFieldId =
  | "date"
  | "balance"
  | "winLossDonut"
  | "moneyDonut"
  | "position"
  | "opsCount"
  | "closedCount"
  | "closedNet"
  | "lastClosed";

export type BacktestCursorFieldId =
  | "date"
  | "price"
  | "position"
  | "entryPrice"
  | "pnl"
  | "open"
  | "high"
  | "low"
  | "close"
  | "changePct"
  | "volume";

export type BacktestHudFieldOption<T extends string> = {
  id: T;
  label: string;
  hint: string;
  /** Always shown; cannot unfavorite. */
  locked?: boolean;
};

export const BACKTEST_GLOBAL_FIELD_OPTIONS: BacktestHudFieldOption<BacktestGlobalFieldId>[] =
  [
    {
      id: "identity",
      label: "Valor · estrategia",
      hint: "Símbolo, estrategia y rango de fechas del análisis.",
    },
    {
      id: "result",
      label: "Resultado %",
      hint: "Retorno total del periodo.",
      locked: true,
    },
    {
      id: "cashFlow",
      label: "Cash → equity",
      hint: "Capital inicial frente al patrimonio final.",
    },
    {
      id: "winLossDonut",
      label: "Donut gan/perd",
      hint: "Proporción de operaciones ganadoras y perdedoras.",
    },
    {
      id: "moneyDonut",
      label: "Donut dinero",
      hint: "Dinero ganado frente a perdido en ops cerradas.",
    },
    {
      id: "drawdown",
      label: "DD (drawdown)",
      hint: "Mayor caída del patrimonio desde un pico hasta un valle.",
    },
    {
      id: "vsBuyHold",
      label: "vs B&H",
      hint: "Diferencia frente a comprar y mantener el valor.",
    },
    {
      id: "opsSummary",
      label: "Ops · cerradas",
      hint: "Número de operaciones y de round-trips cerrados.",
    },
    {
      id: "closedNet",
      label: "Neto ops",
      hint: "Resultado neto aproximado de las operaciones cerradas.",
    },
  ];

export const BACKTEST_TEMPORAL_FIELD_OPTIONS: BacktestHudFieldOption<BacktestTemporalFieldId>[] =
  [
    {
      id: "date",
      label: "Fecha cursor",
      hint: "Fecha de la barra en reproducción o barrido.",
      locked: true,
    },
    {
      id: "balance",
      label: "Balance vivo",
      hint: "Patrimonio y retorno hasta la fecha del cursor.",
    },
    {
      id: "winLossDonut",
      label: "Donut gan/perd",
      hint: "Ganadoras/perdedoras reveladas hasta la fecha.",
    },
    {
      id: "moneyDonut",
      label: "Donut dinero",
      hint: "Dinero en ganadoras/perdedoras hasta la fecha.",
    },
    {
      id: "position",
      label: "Posición",
      hint: "Si hay compra abierta y su P&L no realizado.",
    },
    {
      id: "opsCount",
      label: "Efectuadas",
      hint: "Operaciones reveladas / total del run.",
    },
    {
      id: "closedCount",
      label: "Cerradas",
      hint: "Round-trips cerrados hasta la fecha.",
    },
    {
      id: "closedNet",
      label: "Neto",
      hint: "Neto de ops cerradas hasta la fecha.",
    },
    {
      id: "lastClosed",
      label: "Última cerrada",
      hint: "P&L de la última operación cerrada.",
    },
  ];

export const BACKTEST_CURSOR_FIELD_OPTIONS: BacktestHudFieldOption<BacktestCursorFieldId>[] =
  [
    {
      id: "date",
      label: "Fecha",
      hint: "Fecha de la vela bajo el cursor / reproducción.",
      locked: true,
    },
    {
      id: "price",
      label: "Precio",
      hint: "Precio de cierre (o marca) de esa vela.",
      locked: true,
    },
    {
      id: "position",
      label: "Posición",
      hint: "Comprado o sin posición en esa fecha.",
    },
    {
      id: "entryPrice",
      label: "Precio compra",
      hint: "Precio de entrada de la posición abierta.",
    },
    {
      id: "pnl",
      label: "Beneficio € / %",
      hint: "P&L no realizado de la posición abierta.",
    },
    {
      id: "open",
      label: "Apertura (O)",
      hint: "Apertura de la vela.",
    },
    {
      id: "high",
      label: "Máximo (H)",
      hint: "Máximo de la vela.",
    },
    {
      id: "low",
      label: "Mínimo (L)",
      hint: "Mínimo de la vela.",
    },
    {
      id: "close",
      label: "Cierre (C)",
      hint: "Cierre de la vela.",
    },
    {
      id: "changePct",
      label: "Δ vela",
      hint: "Variación % de la vela (cierre − apertura).",
    },
    {
      id: "volume",
      label: "Volumen",
      hint: "Volumen de la vela si está disponible.",
    },
  ];

export const DEFAULT_GLOBAL_FAVORITES: BacktestGlobalFieldId[] = [
  "identity",
  "result",
  "cashFlow",
  "winLossDonut",
  "moneyDonut",
  "drawdown",
  "vsBuyHold",
  "opsSummary",
  "closedNet",
];

export const DEFAULT_TEMPORAL_FAVORITES: BacktestTemporalFieldId[] = [
  "date",
  "balance",
  "winLossDonut",
  "moneyDonut",
  "position",
  "opsCount",
  "closedCount",
  "closedNet",
  "lastClosed",
];

export const DEFAULT_CURSOR_FAVORITES: BacktestCursorFieldId[] = [
  "date",
  "price",
  "position",
  "entryPrice",
  "pnl",
];

export type BacktestCursorPanelPos = {
  /** Offset from top-left of chart surface, in px. */
  x: number;
  y: number;
};

export type BacktestHudPrefs = {
  globalFavorites: BacktestGlobalFieldId[];
  temporalFavorites: BacktestTemporalFieldId[];
  cursorFavorites: BacktestCursorFieldId[];
  cursorPanelPos: BacktestCursorPanelPos;
};

export const DEFAULT_CURSOR_PANEL_POS: BacktestCursorPanelPos = {
  x: 12,
  y: 12,
};

export const DEFAULT_BACKTEST_HUD_PREFS: BacktestHudPrefs = {
  globalFavorites: DEFAULT_GLOBAL_FAVORITES,
  temporalFavorites: DEFAULT_TEMPORAL_FAVORITES,
  cursorFavorites: DEFAULT_CURSOR_FAVORITES,
  cursorPanelPos: DEFAULT_CURSOR_PANEL_POS,
};

function lockedIds<T extends string>(
  options: BacktestHudFieldOption<T>[],
): Set<T> {
  return new Set(options.filter((o) => o.locked).map((o) => o.id));
}

function sanitizeFavorites<T extends string>(
  raw: unknown,
  options: BacktestHudFieldOption<T>[],
  defaults: T[],
): T[] {
  const valid = new Set(options.map((o) => o.id));
  const locked = lockedIds(options);
  const list = Array.isArray(raw)
    ? (raw.filter(
        (id): id is T => typeof id === "string" && valid.has(id as T),
      ) as T[])
    : [...defaults];
  const set = new Set(list);
  for (const id of locked) set.add(id);
  // Preserve catalog order for stable UI.
  return options.map((o) => o.id).filter((id) => set.has(id));
}

export function loadBacktestHudPrefs(): BacktestHudPrefs {
  if (typeof window === "undefined") return DEFAULT_BACKTEST_HUD_PREFS;
  try {
    const raw = localStorage.getItem(BACKTEST_HUD_PREFS_KEY);
    if (!raw) return DEFAULT_BACKTEST_HUD_PREFS;
    const parsed = JSON.parse(raw) as Partial<BacktestHudPrefs>;
    const pos = parsed.cursorPanelPos;
    return {
      globalFavorites: sanitizeFavorites(
        parsed.globalFavorites,
        BACKTEST_GLOBAL_FIELD_OPTIONS,
        DEFAULT_GLOBAL_FAVORITES,
      ),
      temporalFavorites: sanitizeFavorites(
        parsed.temporalFavorites,
        BACKTEST_TEMPORAL_FIELD_OPTIONS,
        DEFAULT_TEMPORAL_FAVORITES,
      ),
      cursorFavorites: sanitizeFavorites(
        parsed.cursorFavorites,
        BACKTEST_CURSOR_FIELD_OPTIONS,
        DEFAULT_CURSOR_FAVORITES,
      ),
      cursorPanelPos: {
        x:
          typeof pos?.x === "number" && Number.isFinite(pos.x)
            ? pos.x
            : DEFAULT_CURSOR_PANEL_POS.x,
        y:
          typeof pos?.y === "number" && Number.isFinite(pos.y)
            ? pos.y
            : DEFAULT_CURSOR_PANEL_POS.y,
      },
    };
  } catch {
    return DEFAULT_BACKTEST_HUD_PREFS;
  }
}

export function saveBacktestHudPrefs(prefs: BacktestHudPrefs): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(BACKTEST_HUD_PREFS_KEY, JSON.stringify(prefs));
  } catch {
    /* ignore quota */
  }
}

export function patchBacktestHudPrefs(
  patch: Partial<BacktestHudPrefs>,
): BacktestHudPrefs {
  const next = { ...loadBacktestHudPrefs(), ...patch };
  saveBacktestHudPrefs(next);
  return next;
}

export function toggleFavoriteInList<T extends string>(
  current: T[],
  id: T,
  options: BacktestHudFieldOption<T>[],
): T[] {
  const locked = lockedIds(options);
  if (locked.has(id)) return current;
  const set = new Set(current);
  if (set.has(id)) set.delete(id);
  else set.add(id);
  for (const lockedId of locked) set.add(lockedId);
  return options.map((o) => o.id).filter((optionId) => set.has(optionId));
}

export function isFavoriteVisible<T extends string>(
  favorites: T[],
  id: T,
): boolean {
  return favorites.includes(id);
}
