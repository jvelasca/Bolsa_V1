/**
 * Sesión Trading MODO DÍA D (sandbox) — handoff desde Backtesting Finalistas #1.
 *
 * Persistida en `bolsa-dia-d-trading-session-v1`.
 * Incluye modo mesa, gate decisions, autoRunId.
 *
 * `fullBleedMovie` **no se persiste**: al recargar siempre vuelve el layout Trading
 * (watchlist / gráfico / Operaciones). Si se persistiera en true, la página original
 * desaparecía y solo se veía la película DÍA D.
 *
 * @see docs/engineering/backtesting-dia-d-premises-2026-07-31.md
 * @see docs/UI_PREFS_LOCALSTORAGE.md
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
  /** Película a pantalla completa (oculta docks Trading). */
  fullBleedMovie?: boolean;
};

type DiaDTradingSessionState = {
  session: DiaDTradingSession | null;
  enterSession: (session: Omit<DiaDTradingSession, 'mode' | 'autoRunId' | 'gateDecisions' | 'fullBleedMovie'> & {
    mode?: DiaDTradingMode;
    fullBleedMovie?: boolean;
  }) => void;
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
        return { session: { ...rest, fullBleedMovie: false } };
      },
      merge: (persisted, current) => {
        const stored = (persisted ?? {}) as Partial<DiaDTradingSessionState>;
        const session = stored.session
          ? {
              ...stored.session,
              gateDecisions: Array.isArray(stored.session.gateDecisions)
                ? stored.session.gateDecisions
                : [],
              // Never hydrate into full-bleed: restores docks / Operaciones.
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
