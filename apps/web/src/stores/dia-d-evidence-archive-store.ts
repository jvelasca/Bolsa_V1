/**
 * Archivo local Evidence DÍA D (sesión C) — complemento a Fase 2 research_evidence.
 * Cap 30 · dedupe por instrumentId+diaD+mode+endDate · remove + export UI (v0.9).
 *
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md
 * @see features/trading/dia-d-evidence-archive-io.ts
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { DiaDSessionEvidenceV1 } from "@/features/trading/dia-d-session-evidence";

export const DIA_D_EVIDENCE_ARCHIVE_KEY = "bolsa-dia-d-evidence-archive-v1";
export const DIA_D_EVIDENCE_ARCHIVE_MAX = 30;

export type DiaDEvidenceArchiveItem = {
  id: string;
  instrumentId: string;
  symbol: string;
  strategyLabel: string;
  mode: string;
  diaD: string;
  endDate: string;
  savedAt: string;
  /** Id en research_evidence si se persistió en Fase 2. */
  researchEvidenceId: string | null;
  engine: string;
  evidence: DiaDSessionEvidenceV1;
  /** Párrafos narrados (IA) si distintos de la heurística. */
  narrativeParagraphs?: [string, string, string] | null;
};

type DiaDEvidenceArchiveState = {
  items: DiaDEvidenceArchiveItem[];
  save: (
    item: Omit<DiaDEvidenceArchiveItem, "id" | "savedAt"> & {
      id?: string;
      savedAt?: string;
    },
  ) => DiaDEvidenceArchiveItem;
  remove: (id: string) => void;
  forInstrument: (instrumentId: string) => DiaDEvidenceArchiveItem[];
  clear: () => void;
};

function archiveKey(item: {
  instrumentId: string;
  diaD: string;
  endDate: string;
  mode: string;
}): string {
  return `${item.instrumentId}|${item.diaD}|${item.endDate}|${item.mode}`;
}

export const useDiaDEvidenceArchiveStore = create<DiaDEvidenceArchiveState>()(
  persist(
    (set, get) => ({
      items: [],
      save: (input) => {
        const savedAt = input.savedAt ?? new Date().toISOString();
        const id =
          input.id ??
          `dde-${input.instrumentId.slice(0, 8)}-${Date.now().toString(36)}-${Math.random()
            .toString(36)
            .slice(2, 8)}`;
        const nextItem: DiaDEvidenceArchiveItem = {
          id,
          instrumentId: input.instrumentId,
          symbol: input.symbol,
          strategyLabel: input.strategyLabel,
          mode: input.mode,
          diaD: input.diaD,
          endDate: input.endDate,
          savedAt,
          researchEvidenceId: input.researchEvidenceId ?? null,
          engine: input.engine,
          evidence: input.evidence,
          narrativeParagraphs: input.narrativeParagraphs ?? null,
        };
        const key = archiveKey(nextItem);
        set((s) => {
          const filtered = s.items.filter((i) => archiveKey(i) !== key);
          return {
            items: [nextItem, ...filtered].slice(0, DIA_D_EVIDENCE_ARCHIVE_MAX),
          };
        });
        return nextItem;
      },
      remove: (id) =>
        set((s) => ({ items: s.items.filter((i) => i.id !== id) })),
      forInstrument: (instrumentId) =>
        get().items.filter((i) => i.instrumentId === instrumentId),
      clear: () => set({ items: [] }),
    }),
    { name: DIA_D_EVIDENCE_ARCHIVE_KEY },
  ),
);
