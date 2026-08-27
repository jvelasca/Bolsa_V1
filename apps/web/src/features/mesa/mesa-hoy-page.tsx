/**
 * Hoy — inbox diario (ADR-037 + ADR-040 · V1.23 Fase 4).
 *
 * Cuatro bloques: Requiere acción · Oportunidades · Vigilar · Sin acción.
 * Las vistas de detalle salen del chrome (menú «Ver detalles»); los deep-links
 * `?view=` siguen vivos. La firma es el drawer de Confirmar / `/confirm`.
 */

import { useMemo, useRef } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import type { ExitSuggestedActionV1, ProtectPlanV1 } from "@bolsa/shared";
import {
  buildMesaActionQueue,
  buildMesaOperationalHeader,
  buildMesaProtectionState,
  buildMesaDecisionAlerts,
  buildMesaSessionState,
  buildOpportunityRanking,
  buildPortfolioRiskSnapshot,
  buildUnifiedAlertInbox,
  buildInvestmentPositionAggregate,
  computeSectorExposurePct,
  filterMesaAttentionItems,
  mapMesaNextAction,
  mesaEntriesBlocked,
  pickPositionStudies,
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
import { MesaIncidentBanner } from "@/features/operations/mesa-incident-banner";
import {
  portfolioReconStatusFromReport,
  useOpsSelfEval,
} from "@/features/operational-console/use-ops-self-eval";
import { MesaCoberturaKpi } from "@/features/mesa/mesa-cobertura-kpi";
import { MesaInboxBlock } from "@/features/mesa/mesa-inbox-block";
import { MesaHoyDetailsMenu } from "@/features/mesa/mesa-hoy-details-menu";
import { MesaDatosChip } from "@/features/mesa/mesa-datos-chip";
import { MesaOpportunitiesTeaser } from "@/features/mesa/mesa-opportunities-teaser";
import { MesaWatchList } from "@/features/mesa/mesa-watch-list";
import { MesaAttentionQueue } from "@/features/mesa/mesa-attention-queue";
import { MesaPositionsSummary } from "@/features/mesa/mesa-positions-summary";
import { MesaDecisionAlertsPanel } from "@/features/mesa/mesa-decision-alerts-panel";
import { MesaLibroPanel } from "@/features/mesa/mesa-libro-panel";
import { DecisionSpineDetailPanel } from "@/features/mesa/decision-spine-detail-panel";
import { mesaOperationalConsoleHref } from "@/features/mesa/mesa-nav-links";
import { parseHoyView } from "@/features/mesa/mesa-hoy-view";
import { HOY_VIEW, hoyViewHref } from "@/features/confirm/daily-nav";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";
import { DecisionJournalPage } from "@/features/decision-journal/decision-journal-page";
import { api } from "@/lib/api";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

const STUDIES_LIMIT = 200;
const MESA_REFETCH_MS = 60_000;

const EXIT_SUGGESTED_ACTIONS = new Set([
  "hold",
  "protect",
  "reduce",
  "full_exit",
]);

/** El wire trae `suggestedAction` como string; no se asume acción desconocida. */
function parseExitSuggestedAction(
  raw: string | null | undefined,
): ExitSuggestedActionV1 | null {
  if (raw && EXIT_SUGGESTED_ACTIONS.has(raw)) {
    return raw as ExitSuggestedActionV1;
  }
  return null;
}

function formatHoyDate(d = new Date()): string {
  return d.toLocaleDateString(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

export function MesaHoyPage() {
  const accountScope = useActiveAccountQueryKey();
  const { effectiveAccountId, account } = useActiveAccount();
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

  const estudioStatus = estudioUniverseUnavailable
    ? ("unavailable" as const)
    : estudioInstrumentIds.length === 0
      ? ("empty" as const)
      : ("ok" as const);

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
  const incidents = incidentsFailed
    ? []
    : (incidentsQuery.data?.data?.incidents ?? []);

  const entriesBlocked =
    incidentsFailed ||
    mesaEntriesBlocked({
      killSwitchEffective: killOn,
      incidents,
      vetoed,
    });

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

  const protectionDiscrepancies = useMemo(() => {
    const out: Array<{
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
      if (protection.discrepancy) {
        out.push({
          symbol: position.symbol,
          reason: "Discrepancia de protección — stop no confirmado",
          recommendedAction: "REVISAR PROTECCIÓN",
        });
      }
    }
    return out;
  }, [positions, studiesMap, board]);

  const attentionItems = useMemo(() => {
    const queue = buildMesaActionQueue(board);
    return filterMesaAttentionItems(queue, 5, protectionDiscrepancies);
  }, [board, protectionDiscrepancies]);

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
        maxSectorExposurePct: 40,
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
    ],
  );

  const decisionAlerts = useMemo(
    () =>
      buildMesaDecisionAlerts({
        positions,
        studies,
        dataStale: operationalHeader.dataFreshness.state === "stale",
        incidentCount: Math.max(0, incidentCount),
        protectionDiscrepancies: protectionDiscrepancies.map((d) => ({
          symbol: d.symbol,
        })),
      }),
    [
      positions,
      studies,
      operationalHeader.dataFreshness.state,
      incidentCount,
      protectionDiscrepancies,
    ],
  );

  const positionAggregates = useMemo(
    () =>
      positions.map((position) => {
        const { originStudy, evolutionStudy } = pickPositionStudies(
          position,
          studiesByDecision,
          studiesMap,
        );
        const protectPlan = protectPlanByInstrument.get(position.instrumentId);
        return buildInvestmentPositionAggregate({
          position,
          study: evolutionStudy,
          originStudy,
          protectPlan,
        });
      }),
    [positions, studiesMap, studiesByDecision, protectPlanByInstrument],
  );

  const unifiedAlerts = useMemo(
    () =>
      buildUnifiedAlertInbox({
        decisionAlerts,
        positionAggregates,
        portfolioRiskWarnings:
          portfolioRisk.portfolioOpenRiskR != null &&
          portfolioRisk.portfolioOpenRiskR > portfolioRisk.portfolioRiskLimitR
            ? [
                `Riesgo abierto ${portfolioRisk.portfolioOpenRiskR}R supera límite ${portfolioRisk.portfolioRiskLimitR}R`,
              ]
            : [],
      }),
    [decisionAlerts, positionAggregates, portfolioRisk],
  );

  const pendingSignature = Math.max(
    board?.buckets?.pendingConfirm ?? 0,
    board?.semiF3Queue?.length ?? 0,
  );

  /** Posiciones cuya siguiente acción es Proteger / Reducir / Salir. */
  const positionsNeedingAction = useMemo(() => {
    const discrepancySymbols = new Set(
      protectionDiscrepancies.map((d) => d.symbol),
    );
    const out: Array<{ symbol: string; label: string }> = [];
    for (const position of positions) {
      const next = mapMesaNextAction({
        hasOpenPosition: true,
        protectPlan: protectPlanByInstrument.get(position.instrumentId) ?? null,
        exitSuggestedAction: parseExitSuggestedAction(
          position.operational?.exitPlan?.suggestedAction,
        ),
        protectionDiscrepancy: discrepancySymbols.has(position.symbol),
      });
      if (
        next.kind === "protect" ||
        next.kind === "reduce" ||
        next.kind === "exit"
      ) {
        out.push({ symbol: position.symbol, label: next.label });
      }
    }
    return out;
  }, [positions, protectPlanByInstrument, protectionDiscrepancies]);

  const watchRows = useMemo(
    () => opportunityRanking.all.filter((row) => row.category === "WATCH"),
    [opportunityRanking],
  );

  const requiereAccionCount =
    attentionItems.length + pendingSignature + positionsNeedingAction.length;

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
            <MesaInboxBlock
              title="Requiere acción"
              description="Atención, firmas pendientes y posiciones que piden Proteger / Reducir / Salir."
              count={requiereAccionCount}
              emptyLabel="Nada requiere tu acción"
              testId="mesa-inbox-requiere-accion"
            >
              {pendingSignature > 0 ? (
                <div
                  className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm"
                  data-testid="mesa-inbox-f3-pending"
                >
                  <p className="font-medium text-amber-950 dark:text-amber-100">
                    {pendingSignature} pendiente
                    {pendingSignature === 1 ? "" : "s"} de firma
                  </p>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      className="text-xs font-medium text-primary hover:underline"
                      onClick={() => openConfirmDrawer()}
                    >
                      Abrir Confirm
                    </button>
                    <Link
                      to={CONFIRM_PATH}
                      className="text-xs font-medium text-primary hover:underline"
                    >
                      Ir a /confirm
                    </Link>
                  </div>
                </div>
              ) : null}
              <MesaAttentionQueue items={attentionItems} board={board} />
              {positionsNeedingAction.length > 0 ? (
                <ul
                  className="space-y-1 rounded-md border border-border/60 px-3 py-2 text-xs"
                  data-testid="mesa-inbox-positions-action"
                >
                  {positionsNeedingAction.map((row) => (
                    <li key={row.symbol} className="flex justify-between gap-2">
                      <span className="font-medium">{row.symbol}</span>
                      <button
                        type="button"
                        className="text-primary hover:underline"
                        onClick={() => openConfirmDrawer()}
                      >
                        {row.label}
                      </button>
                    </li>
                  ))}
                </ul>
              ) : null}
              <MesaDecisionAlertsPanel
                alerts={decisionAlerts}
                unifiedAlerts={unifiedAlerts}
              />
            </MesaInboxBlock>

            <MesaInboxBlock
              title="Oportunidades"
              description="Calidad del ranking — no es una orden. Confirm firma."
              count={opportunityRanking.top.length}
              emptyLabel="Sin oportunidades TOP"
              testId="mesa-inbox-oportunidades"
            >
              <MesaOpportunitiesTeaser
                rows={opportunityRanking.top}
                entriesBlocked={entriesBlocked}
                operableCount={opportunityRanking.funnel.operableCount}
                verTodasHref={hoyViewHref(HOY_VIEW.oportunidades)}
              />
            </MesaInboxBlock>

            <MesaInboxBlock
              title="Vigilar"
              description="Interesantes todavía no preparadas — sin CTA de compra."
              count={watchRows.length}
              emptyLabel="Nada en vigilancia"
              testId="mesa-inbox-vigilar"
            >
              <MesaWatchList rows={watchRows} />
            </MesaInboxBlock>

            <MesaInboxBlock
              title="Sin acción"
              description="Cobertura Estudio y frescura — información secundaria."
              count={null}
              testId="mesa-inbox-sin-accion"
              headerRight={
                <MesaDatosChip
                  scanUpdatedAt={opportunityRanking.funnel.rankingAsOf}
                />
              }
            >
              <MesaCoberturaKpi
                frescos={
                  estudioStatus === "unavailable"
                    ? 0
                    : opportunityRanking.funnel.analyzedCount
                }
                universeCount={
                  estudioStatus === "unavailable"
                    ? 0
                    : opportunityRanking.funnel.universeCount
                }
                estudioStatus={estudioStatus}
              />
              <div
                className="rounded-md border border-border/60 bg-muted/20 px-4 py-3 text-sm"
                data-testid="mesa-system-health-link"
              >
                <p className="font-medium">
                  Estado operativo: {operationalHeader.operationalStatusLabel}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Salud del sistema, recon e incidentes — solo si hace falta.
                </p>
                <Link
                  to={mesaOperationalConsoleHref()}
                  className="mt-2 inline-block text-xs text-primary hover:underline"
                >
                  Detalles operativos →
                </Link>
              </div>
            </MesaInboxBlock>
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
            />
            <MesaLibroPanel summary={portfolio} accountName={account?.name} />
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
