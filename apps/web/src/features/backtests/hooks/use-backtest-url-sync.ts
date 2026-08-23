/**
 * Deep-links URL + guards listAuto del Hub Backtesting (`/backtests`).
 *
 * Extraído de `backtests-page.tsx` (Track B B5) para reducir el "god component".
 * Cero lógica nueva: mover + tipar.
 */

import {
  useEffect,
  useRef,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from "react";
import type { SetURLSearchParams } from "react-router-dom";
import type { InstrumentListSummaryDto } from "@bolsa/shared";
import type {
  HubTab,
  ResultFocus,
  StrategiesListFilter,
  UniverseMode,
} from "@/features/backtests/backtests-page.constants";
import type { ListAutoCampaign } from "@/features/backtests/backtest-list-auto";
import { parseLibraryNavFromSearch } from "@/features/backtests/library-nav";
import type { MineStrategiesFilterState } from "@/features/backtests/mine-strategies-filters";
import { isOpenAnalysisQuery } from "@/features/backtests/strategy-monitor";
import type { DiaDTradingSession } from "@/stores/dia-d-trading-session-store";

/** Forma mínima de `listsQuery` usada por el deep-link `?listId=`. */
type ListsQueryForUrlSync = {
  isSuccess: boolean;
  data?: { data: InstrumentListSummaryDto[] } | undefined;
};

export type UseBacktestUrlSyncParams = {
  onBacktestsRoute: boolean;
  searchParams: URLSearchParams;
  setResultFocus: Dispatch<SetStateAction<ResultFocus>>;
  setTab: (next: HubTab) => void;
  patchSearchParams: (
    mutate: (params: URLSearchParams) => void,
    opts?: { replace?: boolean },
  ) => void;
  diaDVerifySession: DiaDTradingSession | null;
  setStrategiesListFilter: Dispatch<SetStateAction<StrategiesListFilter>>;
  setLibraryFocusStrategyId: Dispatch<SetStateAction<string | null>>;
  setLibraryFocusPreset: Dispatch<SetStateAction<string | null>>;
  setMineFilters: Dispatch<SetStateAction<MineStrategiesFilterState>>;
  setPreferOpenAnalysis: Dispatch<SetStateAction<boolean>>;
  runIdFromUrl: string | null;
  listAutoRef: MutableRefObject<ListAutoCampaign | null>;
  instrumentId: string;
  setInstrumentId: Dispatch<SetStateAction<string>>;
  listsQuery: ListsQueryForUrlSync;
  setUniverseMode: Dispatch<SetStateAction<UniverseMode>>;
  setListId: Dispatch<SetStateAction<string>>;
  setSearchParams: SetURLSearchParams;
  setSelectedId: Dispatch<SetStateAction<string | null>>;
  detail: { id: string } | null | undefined;
};

export function useBacktestUrlSync(params: UseBacktestUrlSyncParams): void {
  const {
    onBacktestsRoute,
    searchParams,
    setResultFocus,
    setTab,
    patchSearchParams,
    diaDVerifySession,
    setStrategiesListFilter,
    setLibraryFocusStrategyId,
    setLibraryFocusPreset,
    setMineFilters,
    setPreferOpenAnalysis,
    runIdFromUrl,
    listAutoRef,
    instrumentId,
    setInstrumentId,
    listsQuery,
    setUniverseMode,
    setListId,
    setSearchParams,
    setSelectedId,
    detail,
  } = params;

  // Deep-link: ?focus=finalists|coach|lab|detail|fundamental (solo en /backtests)
  useEffect(() => {
    if (!onBacktestsRoute) return;
    const focus = searchParams.get("focus");
    if (
      focus === "coach" ||
      focus === "lab" ||
      focus === "finalists" ||
      focus === "detail" ||
      focus === "fundamental" ||
      focus === "ranking" ||
      focus === "list_auto"
    ) {
      setResultFocus(focus);
    }
  }, [searchParams, onBacktestsRoute]);

  // ADR-019 U2: ?verify=1 → Análisis técnico + host Verificar (sesión LAB)
  useEffect(() => {
    if (!onBacktestsRoute) return;
    if (searchParams.get("verify") !== "1") return;
    setTab("run");
    setResultFocus("detail");
    // setTab/setResultFocus son setters estables de estado; no requieren dep.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, onBacktestsRoute]);

  // Si la URL pide verify pero no hay sesión LAB, quitar el flag (evita pantallas rotas).
  useEffect(() => {
    if (!onBacktestsRoute) return;
    if (searchParams.get("verify") !== "1") return;
    if (diaDVerifySession) return;
    patchSearchParams((params) => {
      params.delete("verify");
    });
    // patchSearchParams se redefine cada render (factory cada render);
    // añadirla como dep re-dispararía el effect. El guard `searchParams` basta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, onBacktestsRoute, diaDVerifySession]);

  // Deep-link Biblioteca: ?tab=strategies&library=&strategyId=&preset=&q=
  useEffect(() => {
    if (!onBacktestsRoute) return;
    const nav = parseLibraryNavFromSearch(searchParams);
    if (!nav) {
      setLibraryFocusStrategyId(null);
      setLibraryFocusPreset(null);
      return;
    }
    setStrategiesListFilter(nav.library);
    setLibraryFocusStrategyId(nav.strategyId ?? null);
    setLibraryFocusPreset(nav.preset ?? null);
    if (nav.q != null) {
      setMineFilters((prev) =>
        prev.query === nav.q ? prev : { ...prev, query: nav.q ?? "" },
      );
    }
  }, [searchParams, onBacktestsRoute]);

  // Deep-link: ?focus=monitor → abrir Monitor Finalistas (CORE-R cola)
  useEffect(() => {
    if (!onBacktestsRoute) return;
    if (searchParams.get("focus") !== "monitor") return;
    setTab("run");
    const id = window.setTimeout(() => {
      const el = document.getElementById("strategy-monitor-hub");
      const details = el?.closest("details");
      if (details) details.open = true;
      el?.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 120);
    return () => window.clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, onBacktestsRoute]);

  // Deep-link: ?openAnalysis=1 (+ runId) → abrir checklist paper (Camino A).
  useEffect(() => {
    if (!onBacktestsRoute || !runIdFromUrl) return;
    if (isOpenAnalysisQuery(searchParams.get("openAnalysis"))) {
      setPreferOpenAnalysis(true);
    }
  }, [searchParams, runIdFromUrl, onBacktestsRoute]);

  useEffect(() => {
    if (!onBacktestsRoute) return;
    // Durante Lista AUTO el valor lo marca la campaña; no dejar que un ?instrumentId=
    // viejo (p.ej. AENA) revierta el estado entre tickers.
    if (listAutoRef.current && !listAutoRef.current.aborted) return;
    const fromUrl = searchParams.get("instrumentId");
    if (fromUrl && fromUrl !== instrumentId) {
      setInstrumentId(fromUrl);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, onBacktestsRoute]);

  // Deep-link: /backtests?listId=… (hub Listas → Backtesting).
  const appliedListIdFromUrlRef = useRef(false);
  useEffect(() => {
    if (!onBacktestsRoute || appliedListIdFromUrlRef.current) return;
    const fromUrl = searchParams.get("listId")?.trim();
    if (!fromUrl) return;
    const lists = listsQuery.data?.data ?? [];
    if (!listsQuery.isSuccess) return;
    if (!lists.some((list) => list.id === fromUrl)) return;
    appliedListIdFromUrlRef.current = true;
    setUniverseMode("list");
    setListId(fromUrl);
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.delete("listId");
        if (!next.get("tab")) next.set("tab", "run");
        return next;
      },
      { replace: true },
    );
  }, [
    onBacktestsRoute,
    searchParams,
    listsQuery.isSuccess,
    listsQuery.data,
    setSearchParams,
  ]);

  // Deep-link: /backtests?runId=… (Research → resultado).
  // Solo reacciona a cambios de la URL — no re-aplicar un runId viejo cuando
  // selectInstrument ya puso selectedId=null y el patch de URL aún no ha llegado.
  useEffect(() => {
    if (!onBacktestsRoute || !runIdFromUrl) return;
    setSelectedId((prev) => (prev === runIdFromUrl ? prev : runIdFromUrl));
  }, [runIdFromUrl, onBacktestsRoute]);

  useEffect(() => {
    if (!runIdFromUrl || !detail?.id || detail.id !== runIdFromUrl) return;
    const el = document.getElementById("backtest-result");
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [runIdFromUrl, detail?.id]);
}
