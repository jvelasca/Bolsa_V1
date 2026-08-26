import type { JournalStudyUserStatus } from "@bolsa/shared";

export type JournalStudyColumnId =
  | "symbol"
  | "status"
  | "period"
  | "opinion"
  | "targets"
  | "strength"
  | "updated"
  | "entry"
  | "vigencia"
  | "actions";

export interface JournalStudyColumnLayoutItem {
  id: JournalStudyColumnId;
  width: number;
  visible: boolean;
}

export type JournalStudySortDirection = "asc" | "desc";

export interface JournalStudySortState {
  columnId: JournalStudyColumnId;
  direction: JournalStudySortDirection;
}

export const JOURNAL_STUDY_COLUMN_LABELS: Record<JournalStudyColumnId, string> =
  {
    symbol: "Activo",
    status: "Estado",
    period: "Periodo",
    opinion: "Opinión",
    targets: "Objetivos",
    strength: "Fuerza",
    updated: "Actualizado",
    entry: "Entrada",
    vigencia: "Vigencia",
    actions: "Acciones",
  };

const MIN_WIDTH = 56;
const MAX_WIDTH = 360;

export function clampJournalStudyColumnWidth(width: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.round(width)));
}

export const DEFAULT_JOURNAL_STUDY_LAYOUT: JournalStudyColumnLayoutItem[] = [
  { id: "symbol", width: 108, visible: true },
  { id: "status", width: 92, visible: true },
  { id: "period", width: 68, visible: true },
  { id: "opinion", width: 72, visible: true },
  { id: "targets", width: 84, visible: true },
  { id: "strength", width: 88, visible: true },
  { id: "updated", width: 104, visible: true },
  { id: "entry", width: 72, visible: false },
  { id: "vigencia", width: 80, visible: false },
  { id: "actions", width: 44, visible: true },
];

export const DEFAULT_JOURNAL_STUDY_FAVORITES: JournalStudyColumnId[] = [
  "symbol",
  "status",
  "opinion",
  "strength",
];

export function visibleJournalStudyColumns(
  layout: JournalStudyColumnLayoutItem[],
): JournalStudyColumnLayoutItem[] {
  return layout.filter((column) => column.visible);
}

export function buildJournalStudyGridTemplate(
  visibleColumns: JournalStudyColumnLayoutItem[],
): string {
  if (visibleColumns.length === 0) return "minmax(0, 1fr)";
  return visibleColumns.map((column) => `${column.width}px`).join(" ");
}

export function journalStudyGridMinWidth(
  visibleColumns: JournalStudyColumnLayoutItem[],
): number {
  return visibleColumns.reduce((sum, column) => sum + column.width, 0);
}

export function journalStudyColumnAlign(
  columnId: JournalStudyColumnId,
): "left" | "right" | "center" {
  if (
    columnId === "symbol" ||
    columnId === "status" ||
    columnId === "period" ||
    columnId === "opinion" ||
    columnId === "vigencia"
  ) {
    return "left";
  }
  if (columnId === "actions") return "center";
  return "right";
}

export function fitJournalStudyColumnsToContent(
  layout: JournalStudyColumnLayoutItem[],
  contentSamples: Partial<Record<JournalStudyColumnId, string[]>>,
): JournalStudyColumnLayoutItem[] {
  const charPx = 6.5;
  const pad = 16;
  return layout.map((column) => {
    const header = JOURNAL_STUDY_COLUMN_LABELS[column.id];
    const headerW = header.length * charPx + pad + 12;
    const samples = contentSamples[column.id] ?? [];
    let contentW = 0;
    for (const sample of samples) {
      if (!sample) continue;
      contentW = Math.max(contentW, sample.length * charPx + pad);
    }
    contentW = Math.max(contentW, header.length * charPx + pad);
    const floor =
      column.id === "actions" ? 40 : column.id === "strength" ? 80 : MIN_WIDTH;
    const width = clampJournalStudyColumnWidth(
      Math.max(floor, headerW, contentW),
    );
    return { ...column, width };
  });
}

export function resizeJournalStudyColumn(
  layout: JournalStudyColumnLayoutItem[],
  columnId: JournalStudyColumnId,
  width: number,
): JournalStudyColumnLayoutItem[] {
  return layout.map((column) =>
    column.id === columnId
      ? { ...column, width: clampJournalStudyColumnWidth(width) }
      : column,
  );
}

export function reorderJournalStudyColumns(
  layout: JournalStudyColumnLayoutItem[],
  fromId: JournalStudyColumnId,
  toId: JournalStudyColumnId,
): JournalStudyColumnLayoutItem[] {
  const fromIndex = layout.findIndex((column) => column.id === fromId);
  const toIndex = layout.findIndex((column) => column.id === toId);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) return layout;
  const next = [...layout];
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved!);
  return next;
}

export function toggleJournalStudyColumn(
  layout: JournalStudyColumnLayoutItem[],
  columnId: JournalStudyColumnId,
): JournalStudyColumnLayoutItem[] {
  if (columnId === "actions" || columnId === "symbol") return layout;
  const next = layout.map((column) =>
    column.id === columnId ? { ...column, visible: !column.visible } : column,
  );
  if (!next.some((column) => column.visible && column.id !== "actions")) {
    return layout;
  }
  return next;
}

export function toggleJournalStudyFavorite(
  favoriteIds: JournalStudyColumnId[],
  columnId: JournalStudyColumnId,
): JournalStudyColumnId[] {
  const current = new Set(favoriteIds);
  if (current.has(columnId)) current.delete(columnId);
  else current.add(columnId);
  return DEFAULT_JOURNAL_STUDY_LAYOUT.map((column) => column.id).filter(
    (id) => id !== "actions" && current.has(id),
  );
}

export function cycleJournalStudySort(
  current: JournalStudySortState | null,
  columnId: JournalStudyColumnId,
): JournalStudySortState | null {
  if (columnId === "actions") return current;
  if (!current || current.columnId !== columnId) {
    return { columnId, direction: "asc" };
  }
  if (current.direction === "asc") return { columnId, direction: "desc" };
  return null;
}

export function isNumericJournalStudyColumn(
  columnId: JournalStudyColumnId,
): boolean {
  return (
    columnId === "strength" || columnId === "targets" || columnId === "entry"
  );
}

const STATUS_ORDER: Record<JournalStudyUserStatus, number> = {
  target_active: 0,
  in_progress: 1,
  target_reached: 2,
  invalidated: 3,
  cancelled: 4,
  no_target: 5,
  neutral: 6,
  closed: 7,
};

export function journalStudyStatusRank(status: string): number {
  return STATUS_ORDER[status as JournalStudyUserStatus] ?? 99;
}

const STORAGE_KEY = "bolsa.journal-study-columns.v2";

export function loadJournalStudyLayout(): {
  layout: JournalStudyColumnLayoutItem[];
  favorites: JournalStudyColumnId[];
} {
  if (typeof window === "undefined") {
    return {
      layout: DEFAULT_JOURNAL_STUDY_LAYOUT,
      favorites: DEFAULT_JOURNAL_STUDY_FAVORITES,
    };
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {
        layout: DEFAULT_JOURNAL_STUDY_LAYOUT,
        favorites: DEFAULT_JOURNAL_STUDY_FAVORITES,
      };
    }
    const parsed = JSON.parse(raw) as {
      layout?: JournalStudyColumnLayoutItem[];
      favorites?: JournalStudyColumnId[];
    };
    const byId = new Map((parsed.layout ?? []).map((item) => [item.id, item]));
    const layout = DEFAULT_JOURNAL_STUDY_LAYOUT.map((item) => {
      const saved = byId.get(item.id);
      return saved
        ? {
            ...item,
            width: clampJournalStudyColumnWidth(saved.width),
            visible: saved.visible,
          }
        : item;
    });
    const order = parsed.layout?.map((item) => item.id) ?? [];
    layout.sort((a, b) => {
      const ai = order.indexOf(a.id);
      const bi = order.indexOf(b.id);
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
    });
    return {
      layout,
      favorites: parsed.favorites ?? DEFAULT_JOURNAL_STUDY_FAVORITES,
    };
  } catch {
    return {
      layout: DEFAULT_JOURNAL_STUDY_LAYOUT,
      favorites: DEFAULT_JOURNAL_STUDY_FAVORITES,
    };
  }
}

export function persistJournalStudyLayout(
  layout: JournalStudyColumnLayoutItem[],
  favorites: JournalStudyColumnId[],
): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ layout, favorites }),
  );
}
