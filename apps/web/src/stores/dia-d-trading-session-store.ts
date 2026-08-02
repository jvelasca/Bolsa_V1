/**
 * Sesión LAB — Verificar D→hoy (sandbox Cartera LAB).
 *
 * Antes: Trading MODO DÍA D. Desde ADR-019 vive en Backtesting (universo LAB).
 * Clave localStorage conservada por compatibilidad de sesiones abiertas.
 *
 * `fullBleedMovie` **no se persiste**.
 *
 * @see docs/adr/019-dual-universes-lab-vs-trading.md
 * @see docs/engineering/dual-universes-lab-trading-design-2026-08-02.md
 */

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export type DiaDTradingMode = 'manual' | 'semi' | 'auto';

export type DiaDGateDecision = {
  tradeId: string;
  timestamp: string;
  side: string;
  price: number;
  action: 'accept' | 'reject';
  decidedAt: string;
};

export type DiaDTradingSession = {
  /** Universo de producto (U5): siempre lab para verificación. */
  universe: 'lab';
  instrumentId: string;
  symbol: string;
  strategyDefinitionId: string;
  strategyLabel: string;
  rank: number;
  /** Hoy simulado (inicio del replay). */
  diaD: string;
  /** Fin del replay (habitualmente hoy real al crear la sesión). */
  endDate: string;
  mode: DiaDTradingMode;
  /** Run Auto cacheado (D→hoy) para no re-lanzar al remontar. */
  autoRunId?: string | null;
  /** Log Semi/Manual: aceptaciones/rechazos. Reescriben fills/equity en v0.4. */
  gateDecisions: DiaDGateDecision[];
  /** Película a pantalla completa (oculta docks del host). */
  fullBleedMovie?: boolean;
};

type DiaDTradingSessionState = {
  session: DiaDTradingSession | null;
  enterSession: (
    session: Omit<
      DiaDTradingSession,
      'mode' | 'autoRunId' | 'gateDecisions' | 'fullBleedMovie' | 'universe'
    > & {
      mode?: DiaDTradingMode;
      fullBleedMovie?: boolean;
      universe?: 'lab';
    },
  ) => void;
  setMode: (mode: DiaDTradingMode) => void;
  setAutoRunId: (autoRunId: string | null) => void;
  setFullBleedMovie: (fullBleed: boolean) => void;
  addGateDecision: (decision: Omit<DiaDGateDecision, 'decidedAt'>) => void;
  clearGateDecisions: () => void;
  exitSession: () => void;
};

export const useDiaDTradingSessionStore = create<DiaDTradingSessionState>()(
  persist(
    (set) => ({
      session: null,
      enterSession: (input) =>
        set({
          session: {
            universe: 'lab',
            instrumentId: input.instrumentId,
            symbol: input.symbol,
            strategyDefinitionId: input.strategyDefinitionId,
            strategyLabel: input.strategyLabel,
            rank: input.rank,
            diaD: input.diaD,
            endDate: input.endDate,
            mode: input.mode ?? 'auto',
            autoRunId: null,
            gateDecisions: [],
            fullBleedMovie: input.fullBleedMovie ?? false,
          },
        }),
      setMode: (mode) =>
        set((s) => (s.session ? { session: { ...s.session, mode } } : s)),
      setAutoRunId: (autoRunId) =>
        set((s) => (s.session ? { session: { ...s.session, autoRunId } } : s)),
      setFullBleedMovie: (fullBleedMovie) =>
        set((s) => (s.session ? { session: { ...s.session, fullBleedMovie } } : s)),
      addGateDecision: (decision) =>
        set((s) => {
          if (!s.session) return s;
          const next = {
            ...decision,
            decidedAt: new Date().toISOString(),
          };
          const without = s.session.gateDecisions.filter((d) => d.tradeId !== decision.tradeId);
          return {
            session: { ...s.session, gateDecisions: [...without, next] },
          };
        }),
      clearGateDecisions: () =>
        set((s) =>
          s.session ? { session: { ...s.session, gateDecisions: [] } } : s,
        ),
      exitSession: () => set({ session: null }),
    }),
    {
      name: 'bolsa-dia-d-trading-session-v1',
      partialize: (s) => {
        if (!s.session) return { session: null };
        const { fullBleedMovie: _omit, ...rest } = s.session;
        return { session: { ...rest, universe: 'lab' as const, fullBleedMovie: false } };
      },
      merge: (persisted, current) => {
        const stored = (persisted ?? {}) as Partial<DiaDTradingSessionState>;
        const session = stored.session
          ? {
              ...stored.session,
              universe: 'lab' as const,
              gateDecisions: Array.isArray(stored.session.gateDecisions)
                ? stored.session.gateDecisions
                : [],
              fullBleedMovie: false,
            }
          : null;
        return { ...current, ...stored, session };
      },
    },
  ),
);

export const DIA_D_MODE_LABELS: Record<DiaDTradingMode, string> = {
  manual: 'Manual',
  semi: 'Semi',
  auto: 'Auto',
};
