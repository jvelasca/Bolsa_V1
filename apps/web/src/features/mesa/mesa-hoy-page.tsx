/**
 * Hoy — Daily Desk 2.0 (ADR-037 + ADR-040 · V1.42 F6).
 *
 * Cuatro cubos §B.7 (requiere acción / oportunidades / vigilar / sin acción).
 * Misma CTA/frase que Mercado (POT/EOT). Sin ranking/KPI en el chrome
 * (no segundo Mercado). Detalles detrás de «Ver detalles» / `?view=`.
 * Confirm = firma (drawer / `/confirm`).
 */

import { useMemo, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import type { ProtectPlanV1 } from "@bolsa/shared";
import {
  buildMesaOperationalHeader,
  aggregateMesaProtectionKpi,
  buildMesaProtectionState,
  buildMesaSessionState,
  buildOpportunityRanking,
  buildPortfolioRiskSnapshot,
  buildDailyDeskInbox,
  buildOperatingDeskInbox,
  computeSectorExposurePct,
  studiesByDecisionIdMap,
  studiesByInstrumentMap,
  ESTUDIO_LIST_ID,
} from "@bolsa/shared";
import {
  DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID,
  MesaCandidatesPanel,
} from "@/features/mesa/mesa-candidates-panel";
import { useEstudioMembershipStore } from "@/stores/estudio-membership-store";
import { Button } from "@/components/ui/button";
import { FeatureErrorBoundary } from "@/components/layout/feature-error-boundary";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useEffectiveTradingPolicy } from "@/features/accounts/use-effective-trading-policy";
import { MesaIncidentBanner } from "@/features/operations/mesa-incident-banner";
import {
  portfolioReconStatusFromReport,
  useOpsSelfEval,
} from "@/features/operational-console/use-ops-self-eval";
import { MesaHoyDetailsMenu } from "@/features/mesa/mesa-hoy-details-menu";
import { MesaDatosChip } from "@/features/mesa/mesa-datos-chip";
import { DailyDeskInbox } from "@/features/mesa/daily-desk-inbox";
import { MesaPositionsSummary } from "@/features/mesa/mesa-positions-summary";
import { MesaLibroPanel } from "@/features/mesa/mesa-libro-panel";
import { DecisionSpineDetailPanel } from "@/features/mesa/decision-spine-detail-panel";
import { mesaOperationalConsoleHref } from "@/features/mesa/mesa-nav-links";
import { parseHoyView } from "@/features/mesa/mesa-hoy-view";
import { useMesaEntriesBlocked } from "@/features/mesa/use-mesa-entries-blocked";
import { loadAutoArm } from "@/features/trading/demo-book-auto-arm";
import { resolvePaperAutoPosture } from "@/features/trading/resolve-paper-auto-posture";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { usePendingOrders } from "@/features/trading/use-pending-orders";
import { HOY_VIEW, hoyViewHref } from "@/features/confirm/daily-nav";
import { DecisionJournalPage } from "@/features/decision-journal/decision-journal-page";
import { api } from "@/lib/api";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

const STUDIES_LIMIT = 200;
const MESA_REFETCH_MS = 60_000;

function formatHoyDate(d = new Date()): string {
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

function todayIso(d = new Date()): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function MesaHoyPage() {
  const accountScope = useActiveAccountQueryKey();
  const { effectiveAccountId, account } = useActiveAccount();
  const bookPrefs = useDemoBookPrefs();
  const autoArmed = loadAutoArm().armed;
  const { maxSectorExposurePct } = useEffectiveTradingPolicy();
  const [searchParams] = useSearchParams();
  const view = parseHoyView(
    searchParams.get("view"),
    searchParams.get("focus"),
  );
  const libroRef = useRef<HTMLDivElement | null>(null);

  const selfEvalQuery = useOpsSelfEval(effectiveAccountId);
  const portfolioReconStatus = portfolioReconStatusFromReport(
    selfEvalQuery.data,
  );
  const { entriesBlocked } = useMesaEntriesBlocked();
  const { pendingOrders } = usePendingOrders();

  const boardQuery = useQuery({
    queryKey: ["decision-board", accountScope],
    queryFn: () => api.getDecisionBoard(accountScope!),
    enabled: Boolean(accountScope),
    staleTime: 15_000,
    refetchInterval: MESA_REFETCH_MS,
  });

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
    refetchInterval: MESA_REFETCH_MS,
  });

  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: () => api.getAccountSummary(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
    refetchInterval: MESA_REFETCH_MS,
  });

  const killQuery = useQuery({
    queryKey: ["risk-kill-switch"],
    queryFn: () => api.getRiskKillSwitch(),
    staleTime: 15_000,
    refetchInterval: MESA_REFETCH_MS,
  });

  const studiesQuery = useQuery({
    queryKey: ["decision-studies", effectiveAccountId, "mesa"],
    queryFn: () =>
      api.getDecisionStudies(effectiveAccountId!, { limit: STUDIES_LIMIT }),
    enabled: Boolean(effectiveAccountId),
    staleTime: 30_000,
    refetchInterval: MESA_REFETCH_MS,
  });

  const instrumentsQuery = useQuery({
    queryKey: ["instruments", "mesa-sector"],
    queryFn: api.getInstruments,
    staleTime: 5 * 60_000,
  });

  const incidentsQuery = useQuery({
    queryKey: ["operational-incidents-active", effectiveAccountId],
    queryFn: () => api.getActiveOperationalIncidents(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
    refetchInterval: MESA_REFETCH_MS,
  });

  const scanJobsQuery = useQuery({
    queryKey: ["scan-jobs", "mesa-opportunity"],
    queryFn: api.getScanJobs,
    staleTime: 30_000,
    refetchInterval: MESA_REFETCH_MS,
  });

  const universeListId = DEFAULT_OPPORTUNITY_UNIVERSE_LIST_ID;

  const universeListQuery = useQuery({
    queryKey: ["lists", universeListId, "mesa-opportunity"],
    queryFn: () => api.getList(universeListId),
    staleTime: 5 * 60_000,
  });

  const estudioMembers = useEstudioMembershipStore((s) => s.members);
  const estudioUniverseUnavailable = universeListQuery.isError;
  const estudioInstrumentIds = useMemo(() => {
    // Fail-closed: API error ≠ empty universe (no inventar 0 candidatos).
    if (estudioUniverseUnavailable) return [] as string[];
    const fromApi = universeListQuery.data?.data?.instrumentIds;
    if (fromApi) return fromApi;
    return estudioMembers.map((m) => m.instrumentId);
  }, [estudioUniverseUnavailable, universeListQuery.data, estudioMembers]);

  const dailyOpsQuery = useQuery({
    queryKey: ["paper-desk-daily-report", effectiveAccountId, "mesa-hoy"],
    queryFn: () =>
      api.getPaperDeskDailyReport(effectiveAccountId!, {
        asOf: todayIso(),
      }),
    enabled: Boolean(effectiveAccountId),
    staleTime: 60_000,
    refetchInterval: MESA_REFETCH_MS,
  });
  const autoDesk = dailyOpsQuery.data?.data?.autoDesk ?? null;

  const board = boardQuery.data?.data;
  const portfolio = portfolioQuery.data?.data;
  const studies = useMemo(
    () => studiesQuery.data?.data?.studies ?? [],
    [studiesQuery.data],
  );
  const studiesMap = useMemo(() => studiesByInstrumentMap(studies), [studies]);
  const studiesByDecision = useMemo(
    () => studiesByDecisionIdMap(studies),
    [studies],
  );

  const sectorByInstrumentId = useMemo(() => {
    const out: Record<string, string | null | undefined> = {};
    for (const inst of instrumentsQuery.data?.data ?? []) {
      if (inst.id) out[inst.id] = inst.sector;
    }
    return out;
  }, [instrumentsQuery.data]);

  const killOn = killQuery.data?.effective === true;
  const vetoed = board?.buckets?.vetoed ?? 0;
  const incidentsFailed = incidentsQuery.isError;
  const incidentCount = incidentsFailed
    ? -1
    : (incidentsQuery.data?.data?.incidents?.length ?? 0);

  const sessionState = useMemo(
    () =>
      buildMesaSessionState(board, {
        entriesBlocked,
        killSwitchEffective: killOn,
        incidentCount: Math.max(0, incidentCount),
        estudioUniverseCount:
          universeListQuery.data?.data?.instrumentIds?.length ??
          estudioInstrumentIds.length,
      }),
    [
      board,
      entriesBlocked,
      killOn,
      incidentCount,
      universeListQuery.data,
      estudioInstrumentIds.length,
    ],
  );

  const positions = portfolio?.positions ?? [];

  const mesaFreshnessInstrumentId = positions[0]?.instrumentId ?? null;
  const mesaDataStatusQuery = useQuery({
    queryKey: ["mesa-data-freshness", mesaFreshnessInstrumentId],
    queryFn: () => api.getDataStatus(mesaFreshnessInstrumentId!),
    enabled: Boolean(mesaFreshnessInstrumentId),
    staleTime: 60_000,
    refetchInterval: MESA_REFETCH_MS,
  });
  const mesaLastBarDate = mesaDataStatusQuery.data?.data?.lastBarDate ?? null;

  const portfolioRisk = useMemo(
    () =>
      buildPortfolioRiskSnapshot({
        positions: positions.map((p) => {
          const study = studiesMap.get(p.instrumentId) ?? null;
          return {
            avgCost: p.avgCost,
            quantity: p.quantity,
            lastPrice: p.lastPrice,
            marketValue: p.marketValue,
            sector: p.sector ?? sectorByInstrumentId[p.instrumentId] ?? null,
            operational: p.operational,
            study,
          };
        }),
      }),
    [positions, studiesMap, sectorByInstrumentId],
  );

  const sectorExposurePct = useMemo(
    () =>
      computeSectorExposurePct(
        positions.map((p) => ({
          marketValue: p.marketValue,
          sector: p.sector ?? sectorByInstrumentId[p.instrumentId] ?? null,
        })),
        portfolio?.totalEquity ?? null,
      ),
    [positions, sectorByInstrumentId, portfolio?.totalEquity],
  );

  const riskPositions = useMemo(
    () =>
      positions.map((p) => ({
        avgCost: p.avgCost,
        quantity: p.quantity,
        lastPrice: p.lastPrice,
        marketValue: p.marketValue,
        sector: p.sector ?? sectorByInstrumentId[p.instrumentId] ?? null,
        operational: p.operational,
        study: studiesMap.get(p.instrumentId) ?? null,
      })),
    [positions, sectorByInstrumentId, studiesMap],
  );

  const protectionByPosition = useMemo(() => {
    const states: ReturnType<typeof buildMesaProtectionState>[] = [];
    const discrepancies: Array<{
      symbol: string;
      reason: string;
      recommendedAction: string;
    }> = [];
    for (const position of positions) {
      const study = studiesMap.get(position.instrumentId) ?? null;
      const protectPlan = (() => {
        for (const session of board?.decisionSessions ?? []) {
          if (session.instrumentId === position.instrumentId) {
            const plan = session.protectPlan as ProtectPlanV1 | undefined;
            if (plan?.status === "protect_hint") return plan;
          }
        }
        return null;
      })();
      const protection = buildMesaProtectionState({
        study,
        exitSuggestedStop:
          position.operational?.exitPlan?.suggestedStop ?? null,
        currentStop: position.operational?.currentStop ?? null,
        protectPlan,
      });
      states.push(protection);
      if (protection.discrepancy) {
        discrepancies.push({
          symbol: position.symbol,
          reason: "Discrepancia de protección — stop no confirmado",
          recommendedAction: "REVISAR PROTECCIÓN",
        });
      }
    }
    return {
      states,
      discrepancies,
      kpi: aggregateMesaProtectionKpi(states),
    };
  }, [positions, studiesMap, board]);

  const protectionDiscrepancies = protectionByPosition.discrepancies;
  const protectionKpi = protectionByPosition.kpi;

  const latestCompletedScan = useMemo(() => {
    const jobs = scanJobsQuery.data?.data ?? [];
    const completed = jobs
      .filter((j) => {
        if (j.status !== "completed" || !j.result) return false;
        const listId = j.payload?.universe?.listId ?? null;
        // Prefer Estudio (or discovery jobs tagged for Estudio). Never take
        // an arbitrary IBEX/Lab scan as the daily TRADING universe.
        return listId === ESTUDIO_LIST_ID || listId === universeListId;
      })
      .sort(
        (a, b) =>
          new Date(b.completedAt ?? b.updatedAt).getTime() -
          new Date(a.completedAt ?? a.updatedAt).getTime(),
      );
    return completed[0] ?? null;
  }, [scanJobsQuery.data, universeListId]);

  const opportunityRanking = useMemo(() => {
    const scanResult = latestCompletedScan?.result ?? null;
    const universeCount =
      universeListQuery.data?.data?.instrumentIds?.length ??
      estudioInstrumentIds.length;
    return buildOpportunityRanking({
      studies,
      scanHits: (scanResult?.hits ?? []).map((h) => ({
        instrumentId: h.instrumentId,
        symbol: h.symbol,
      })),
      screenedCount: scanResult?.scannedCount ?? 0,
      hitCount: scanResult?.hitCount ?? scanResult?.hits?.length ?? 0,
      universeCount,
      universeListId,
      scanUpdatedAt:
        latestCompletedScan?.completedAt ??
        latestCompletedScan?.updatedAt ??
        null,
      marketDataAsOf: mesaLastBarDate,
      board: board ?? null,
      estudioInstrumentIds,
      priorityCtx: {
        entriesBlocked,
        portfolioRisk,
        sectorExposurePct,
        sectorByInstrumentId,
        maxSectorExposurePct,
      },
    });
  }, [
    studies,
    latestCompletedScan,
    universeListQuery.data,
    universeListId,
    estudioInstrumentIds,
    board,
    entriesBlocked,
    portfolioRisk,
    sectorExposurePct,
    sectorByInstrumentId,
    mesaLastBarDate,
    maxSectorExposurePct,
  ]);

  const protectPlanByInstrument = useMemo(() => {
    const map = new Map<string, ProtectPlanV1>();
    for (const session of board?.decisionSessions ?? []) {
      const plan = session.protectPlan as ProtectPlanV1 | undefined;
      if (plan?.status === "protect_hint" && session.instrumentId) {
        map.set(session.instrumentId, plan);
      }
    }
    return map;
  }, [board]);

  const operationalHeader = useMemo(
    () =>
      buildMesaOperationalHeader({
        regimeHint: sessionState.regimeHint,
        positions: positions.map((p) => ({
          avgCost: p.avgCost,
          quantity: p.quantity,
          lastPrice: p.lastPrice,
          marketValue: p.marketValue,
          operational: p.operational,
          study: studiesMap.get(p.instrumentId) ?? null,
        })),
        cash: summaryQuery.data?.data?.cash ?? null,
        equity: portfolio?.totalEquity ?? null,
        killSwitchEffective: killOn,
        incidentCount: Math.max(0, incidentCount),
        entriesBlocked,
        vetoed,
        lastBarDate: mesaLastBarDate,
        noFreshnessProbe: positions.length === 0,
        freshnessPartialSample:
          positions.length > 1 && mesaFreshnessInstrumentId
            ? { probed: 1, total: positions.length }
            : null,
        boardQueryFailed: boardQuery.isError,
        incidentsQueryFailed: incidentsFailed,
        portfolioQueryFailed: portfolioQuery.isError,
        summaryQueryFailed: summaryQuery.isError,
        studiesQueryFailed: studiesQuery.isError,
        killQueryFailed: killQuery.isError,
        selfEvalQueryFailed: selfEvalQuery.isError,
        brokerVenue: killQuery.data?.brokerVenue ?? null,
        paperDExecuteEnv: killQuery.data?.paperDExecuteEnv === true,
        readinessState: selfEvalQuery.data?.operationalReadiness?.state ?? null,
        bookMode: bookPrefs.mode,
        autoArmed,
      }),
    [
      sessionState.regimeHint,
      positions,
      studiesMap,
      summaryQuery.data,
      portfolio,
      killOn,
      incidentCount,
      entriesBlocked,
      vetoed,
      mesaLastBarDate,
      boardQuery.isError,
      incidentsFailed,
      portfolioQuery.isError,
      summaryQuery.isError,
      studiesQuery.isError,
      killQuery.isError,
      selfEvalQuery.isError,
      killQuery.data,
      selfEvalQuery.data,
      bookPrefs.mode,
      autoArmed,
    ],
  );

  const pendingSignature = Math.max(
    board?.buckets?.pendingConfirm ?? 0,
    board?.semiF3Queue?.length ?? 0,
  );

  const pendingInstrumentIds = useMemo(
    () => pendingOrders.map((order) => order.instrumentId).filter(Boolean),
    [pendingOrders],
  );

  const confirmQueueInstrumentIds = useMemo(() => {
    const ids: string[] = [];
    for (const row of board?.semiF3Queue ?? []) {
      if (row.instrumentId) ids.push(row.instrumentId);
    }
    return ids;
  }, [board]);

  const paperAutoPosture = useMemo(
    () =>
      resolvePaperAutoPosture({
        bookMode: bookPrefs.mode,
        autoArmed,
        paperDExecuteEnv: killQuery.data?.paperDExecuteEnv === true,
      }),
    [bookPrefs.mode, autoArmed, killQuery.data?.paperDExecuteEnv],
  );

  const dailyDesk = useMemo(() => {
    const baseInput = {
      positions,
      board,
      portfolioReconStatus,
      pendingConfirm: pendingSignature,
      protectionDiscrepancies,
      pendingInstrumentIds,
      studiesByInstrument: studiesMap,
      confirmQueueInstrumentIds,
      entriesBlocked,
      hasOpenIncident: incidentCount > 0,
      protectPlanByInstrument,
    };
    if (autoDesk) {
      return buildOperatingDeskInbox({
        ...baseInput,
        autoDesk,
        exceptionFacts: autoDesk.exceptionFacts ?? [],
        paperAuto: paperAutoPosture,
      });
    }
    return buildDailyDeskInbox(baseInput);
  }, [
    positions,
    board,
    portfolioReconStatus,
    pendingSignature,
    protectionDiscrepancies,
    pendingInstrumentIds,
    studiesMap,
    confirmQueueInstrumentIds,
    entriesBlocked,
    incidentCount,
    protectPlanByInstrument,
    autoDesk,
    paperAutoPosture,
  ]);

  const isRefreshing =
    boardQuery.isFetching ||
    portfolioQuery.isFetching ||
    studiesQuery.isFetching ||
    incidentsQuery.isFetching;

  function refreshAll() {
    void boardQuery.refetch();
    void portfolioQuery.refetch();
    void summaryQuery.refetch();
    void studiesQuery.refetch();
    void killQuery.refetch();
    void incidentsQuery.refetch();
    void selfEvalQuery.refetch();
    void dailyOpsQuery.refetch();
  }

  return (
    <FeatureErrorBoundary
      featureName="Hoy"
      fallbackMessage="No se pudo mostrar Hoy. Tus posiciones siguen intactas en Cartera."
    >
      <div
        className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6"
        data-testid="mesa-hoy-page"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-serif text-2xl font-semibold tracking-tight">
              Hoy
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {formatHoyDate()}
              {account ? ` · ${account.name}` : ""} — ¿qué debo hacer?
            </p>
            <div className="mt-2">
              <MesaDatosChip
                scanUpdatedAt={opportunityRanking.funnel.rankingAsOf}
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={refreshAll}
              disabled={isRefreshing}
            >
              <RefreshCw
                className={`mr-1.5 h-3.5 w-3.5 ${isRefreshing ? "animate-spin" : ""}`}
              />
              Actualizar
            </Button>
            <MesaHoyDetailsMenu />
          </div>
        </div>

        {view !== HOY_VIEW.resumen ? (
          <Link
            to={hoyViewHref(HOY_VIEW.resumen)}
            className="inline-block text-xs text-primary hover:underline"
            data-testid="hoy-back-to-inbox"
          >
            ← Volver a Hoy
          </Link>
        ) : null}

        {incidentsFailed ? (
          <div
            role="alert"
            aria-live="assertive"
            className="rounded-md border border-amber-500/50 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-100"
            data-testid="mesa-incidents-query-error"
          >
            No se pudo consultar incidentes operativos. Se trata como bloqueo
            preventivo hasta confirmar el estado del sistema.
          </div>
        ) : null}

        {effectiveAccountId && incidentCount > 0 ? (
          <div data-testid="mesa-incident-section">
            <MesaIncidentBanner
              accountId={effectiveAccountId}
              portfolioReconStatus={portfolioReconStatus}
              className="border-rose-500/50 bg-rose-500/10"
            />
            <p
              className="mt-2 text-xs font-medium text-rose-700 dark:text-rose-300"
              role="alert"
              aria-live="assertive"
            >
              Nuevas entradas: BLOQUEADAS · Automatismos: BLOQUEADOS ·
              Posiciones: VISIBLES · Desriesgo humano: DISPONIBLE
            </p>
            <Link
              to={mesaOperationalConsoleHref()}
              className="mt-2 inline-block text-xs text-primary hover:underline"
            >
              Detalles operativos →
            </Link>
          </div>
        ) : null}

        {view === HOY_VIEW.resumen ? (
          <div className="space-y-6" data-testid="hoy-inbox">
            <DailyDeskInbox
              inbox={dailyDesk}
              positions={positions}
              protectPlanByInstrument={protectPlanByInstrument}
            />

            <div
              className="flex flex-wrap items-center justify-between gap-3 rounded-md border border-border/60 bg-muted/15 px-3 py-2 text-xs"
              data-testid="daily-desk-footer"
            >
              <div className="space-y-0.5">
                <p className="font-medium text-foreground">
                  Estado: {operationalHeader.operationalStatusLabel}
                </p>
                <p className="text-muted-foreground">
                  Ranking Estudio, Libro, Decisiones y Consola viven en Ver
                  detalles — Hoy no es Mercado.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link
                  to={hoyViewHref(HOY_VIEW.oportunidades)}
                  className="text-primary hover:underline"
                  data-testid="daily-desk-link-oportunidades"
                >
                  Oportunidades
                  {opportunityRanking.top.length > 0
                    ? ` (${opportunityRanking.top.length})`
                    : ""}{" "}
                  →
                </Link>
                <Link
                  to={mesaOperationalConsoleHref()}
                  className="text-primary hover:underline"
                  data-testid="daily-desk-link-consola"
                >
                  Consola →
                </Link>
              </div>
            </div>
          </div>
        ) : null}

        {view === HOY_VIEW.posiciones ? (
          <div
            ref={libroRef}
            className="space-y-4"
            data-testid="hoy-view-posiciones"
          >
            <MesaPositionsSummary
              positions={positions}
              protectPlanByInstrument={protectPlanByInstrument}
              studiesByInstrument={studiesMap}
              studiesByDecisionId={studiesByDecision}
              portfolioReconStatus={portfolioReconStatus}
            />
            <MesaLibroPanel
              summary={portfolio}
              accountName={account?.name}
              protectionKpi={protectionKpi}
            />
          </div>
        ) : null}

        {view === HOY_VIEW.oportunidades ? (
          <div data-testid="hoy-view-oportunidades">
            <MesaCandidatesPanel
              ranking={opportunityRanking}
              entriesBlocked={entriesBlocked}
              portfolioRisk={portfolioRisk}
              sectorExposurePct={sectorExposurePct}
              sectorByInstrumentId={sectorByInstrumentId}
              positions={riskPositions}
              equity={portfolio?.totalEquity ?? null}
              cash={summaryQuery.data?.data?.cash ?? null}
              universeListId={universeListId}
              maxSectorExposurePct={maxSectorExposurePct}
            />
          </div>
        ) : null}

        {view === HOY_VIEW.decisiones ? (
          <div data-testid="hoy-view-decisiones">
            <DecisionSpineDetailPanel
              board={board}
              entriesBlocked={entriesBlocked}
              isLoading={boardQuery.isLoading}
              isError={boardQuery.isError}
            />
          </div>
        ) : null}

        {view === HOY_VIEW.journal ? (
          <div data-testid="hoy-view-journal" className="-mx-4 sm:-mx-6">
            <DecisionJournalPage />
          </div>
        ) : null}
      </div>
    </FeatureErrorBoundary>
  );
}
