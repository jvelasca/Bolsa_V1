/**
 * Cola supervisada F3 (sessionStorage vía zustand persist).
 *
 * Entradas: scan · Finalistas (C) · chart · alarm inbox · manual → propose → Confirm.
 * Campo `origin` + `resolveSupervisedQueueOrigin` alimentan badges en
 * `supervised-f3-panel.tsx`. Cap 40 ítems (preprend; el primero es el más reciente).
 *
 * `openHelpAiPlatform({ panel: 'supervised-f3' })` abre Ayuda → Plataforma IA
 * y hace scroll al panel Confirm (escuchado por `app-help-menu.tsx`).
 *
 * Persistencia: sessionStorage (cache) + BD `supervised_f3_account_state`
 * vía `supervised-f3-sync.ts` (hydrate/push por cuenta Activa).
 *
 * @see docs/engineering/semi-demo-book-impl-slice1-2026-08-03.md
 * @see PAPER_PATH_SUPERVISED
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  AssessmentV1,
  EvidenceAssessmentV1,
  FundamentalAssessmentV1,
  MacroAssessmentV1,
  NewsAssessmentV1,
  RecommendationV1,
  TechnicalAssessmentV1,
} from "@bolsa/shared";

export type SupervisedProposePayload = RecommendationV1 & {
  technicalAssessment?: TechnicalAssessmentV1;
  fundamentalAssessment?: FundamentalAssessmentV1;
  macroAssessment?: MacroAssessmentV1;
  evidenceAssessment?: EvidenceAssessmentV1;
  newsAssessment?: NewsAssessmentV1;
  assessments?: AssessmentV1[];
  decisionPackage?: Record<string, unknown>;
  policyGate?: { status?: string; mode?: string; message?: string } | null;
  lastClose?: number | null;
  source?: string;
  /** Estrategia / señal de origen (Finalistas / Radar) para tenure Mandato. */
  strategyOrSignalRef?: string | null;
  strategyLabel?: string | null;
  decisionSession?: import("@bolsa/shared").DecisionSessionV1;
  weightContext?: import("@bolsa/shared").WeightContextV1;
  combinedScore?: number;
};

export type SupervisedQueueOrigin =
  | "scan"
  | "finalists"
  | "chart"
  | "manual"
  | "alarm"
  | "operativa"
  | "asesor";

export type SupervisedEnqueueMeta = {
  scanId?: string;
  symbol?: string;
  origin?: SupervisedQueueOrigin;
};

export interface SupervisedQueueItem {
  id: string;
  enqueuedAt: string;
  scanId?: string;
  symbol?: string;
  origin?: SupervisedQueueOrigin;
  payload: SupervisedProposePayload;
}

interface SupervisedF3QueueState {
  items: SupervisedQueueItem[];
  activeId: string | null;
  enqueue: (
    payload: SupervisedProposePayload,
    meta?: SupervisedEnqueueMeta,
  ) => string;
  enqueueMany: (
    payloads: SupervisedProposePayload[],
    meta?: Omit<SupervisedEnqueueMeta, "symbol">,
  ) => number;
  remove: (id: string) => void;
  /** ADR-024: quitar de Estudio → saca propuestas abiertas de ese instrumento. */
  removeForInstrument: (instrumentId: string) => number;
  clear: () => void;
  setActive: (id: string | null) => void;
  activeItem: () => SupervisedQueueItem | null;
}

export function resolveSupervisedQueueOrigin(
  item: Pick<SupervisedQueueItem, "origin" | "scanId" | "payload">,
): SupervisedQueueOrigin {
  if (item.origin) return item.origin;
  if (item.payload.source === "finalists") return "finalists";
  if (item.scanId?.startsWith("finalists:")) return "finalists";
  if (item.payload.source === "chart") return "chart";
  if (item.payload.source === "alarm") return "alarm";
  if (item.payload.source === "operativa") return "operativa";
  if (item.payload.source === "asesor_alarma") return "asesor";
  if (item.scanId) return "scan";
  return "manual";
}

export function supervisedQueueOriginLabel(
  origin: SupervisedQueueOrigin,
): string {
  switch (origin) {
    case "finalists":
      return "Finalistas";
    case "scan":
      return "Scan";
    case "chart":
      return "Gráfico";
    case "alarm":
      return "Alarma Radar";
    case "operativa":
      return "Operativa";
    case "asesor":
      return "Asesor";
    default:
      return "Manual";
  }
}

export const useSupervisedF3QueueStore = create<SupervisedF3QueueState>()(
  persist(
    (set, get) => ({
      items: [],
      activeId: null,
      enqueue: (payload, meta) => {
        const id = `q-${payload.recommendationId}-${Date.now()}`;
        const origin =
          meta?.origin ??
          resolveSupervisedQueueOrigin({
            origin: undefined,
            scanId: meta?.scanId,
            payload,
          });
        set((s) => ({
          items: [
            {
              id,
              enqueuedAt: new Date().toISOString(),
              scanId: meta?.scanId,
              symbol: meta?.symbol ?? payload.symbol ?? undefined,
              origin,
              payload,
            },
            ...s.items,
          ].slice(0, 40),
          activeId: s.activeId ?? id,
        }));
        return id;
      },
      enqueueMany: (payloads, meta) => {
        let n = 0;
        for (const p of payloads) {
          get().enqueue(p, {
            scanId: meta?.scanId,
            origin: meta?.origin,
            symbol: p.symbol ?? undefined,
          });
          n += 1;
        }
        return n;
      },
      remove: (id) =>
        set((s) => {
          const items = s.items.filter((i) => i.id !== id);
          const activeId =
            s.activeId === id ? (items[0]?.id ?? null) : s.activeId;
          return { items, activeId };
        }),
      removeForInstrument: (instrumentId) => {
        if (!instrumentId) return 0;
        let n = 0;
        set((s) => {
          const items = s.items.filter((i) => {
            if (i.payload.instrumentId !== instrumentId) return true;
            n += 1;
            return false;
          });
          const activeStill = items.some((i) => i.id === s.activeId);
          return {
            items,
            activeId: activeStill ? s.activeId : (items[0]?.id ?? null),
          };
        });
        return n;
      },
      clear: () => set({ items: [], activeId: null }),
      setActive: (id) => set({ activeId: id }),
      activeItem: () => {
        const s = get();
        return s.items.find((i) => i.id === s.activeId) ?? s.items[0] ?? null;
      },
    }),
    { name: "bolsa-supervised-f3-queue" },
  ),
);

export type OpenHelpAiPlatformOpts = {
  /** Scroll/focus al panel Supervisado F3 en Ayuda → Plataforma IA. */
  panel?: "supervised-f3";
};

/** Abre Ayuda → Plataforma IA (escuchado por AppHelpMenu). */
export function openHelpAiPlatform(opts?: OpenHelpAiPlatformOpts) {
  window.dispatchEvent(
    new CustomEvent("bolsa:open-help", {
      detail: { section: "ai", panel: opts?.panel },
    }),
  );
}
