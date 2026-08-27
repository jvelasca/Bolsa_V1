/**
 * Mesa · Hoy — home operativa diaria (ADR-037 + V1.16 desk).
 */

import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import type { ProtectPlanV1 } from "@bolsa/shared";
import {
  buildMesaActionQueue,
  buildMesaCandidateGroups,
  buildMesaOperationalHeader,
  buildMesaProtectionState,
  buildMesaDecisionAlerts,
  buildMesaSessionState,
  buildPortfolioRiskSnapshot,
  buildUnifiedAlertInbox,
  buildInvestmentPositionAggregate,
  computeSectorExposurePct,
  filterMesaAttentionItems,
  mesaEntriesBlocked,
  studiesByInstrumentMap,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { FeatureErrorBoundary } from "@/components/layout/feature-error-boundary";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { MesaIncidentBanner } from "@/features/operations/mesa-incident-banner";
import {
  portfolioReconStatusFromReport,
  useOpsSelfEval,
} from "@/features/operational-console/use-ops-self-eval";
import { MesaOperationalHeaderStrip } from "@/features/mesa/mesa-operational-header";
import { MesaSessionStateCard } from "@/features/mesa/mesa-session-state-card";
import { MesaLevelSection } from "@/features/mesa/mesa-level-section";
import { MesaAttentionQueue } from "@/features/mesa/mesa-attention-queue";
import { MesaPositionsSummary } from "@/features/mesa/mesa-positions-summary";
import { MesaCandidatesPanel } from "@/features/mesa/mesa-candidates-panel";
import { MesaDecisionAlertsPanel } from "@/features/mesa/mesa-decision-alerts-panel";
import { mesaOperationalConsoleHref } from "@/features/mesa/mesa-nav-links";
import { api } from "@/lib/api";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

const STUDIES_LIMIT = 200;
const MESA_REFETCH_MS = 60_000;

export function MesaHoyPage() {
  const accountScope = useActiveAccountQueryKey();
  const { effectiveAccountId, account } = useActiveAccount();
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

  const board = boardQuery.data?.data;
  const portfolio = portfolioQuery.data?.data;
  const studies = useMemo(
    () => studiesQuery.data?.data?.studies ?? [],
    [studiesQuery.data],
  );
  const studiesMap = useMemo(() => studiesByInstrumentMap(studies), [studies]);

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
      }),
    [board, entriesBlocked, killOn, incidentCount],
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

  const candidateGroups = useMemo(
    () => buildMesaCandidateGroups(board, studiesMap, entriesBlocked),
    [board, studiesMap, entriesBlocked],
  );

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
        const study = studiesMap.get(position.instrumentId) ?? null;
        const protectPlan = protectPlanByInstrument.get(position.instrumentId);
        return buildInvestmentPositionAggregate({
          position,
          study,
          protectPlan,
        });
      }),
    [positions, studiesMap, protectPlanByInstrument],
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
      featureName="Mesa · Hoy"
      fallbackMessage="No se pudo mostrar la mesa. Tus posiciones siguen intactas en el libro."
    >
      <div
        className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6"
        data-testid="mesa-hoy-page"
      >
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="font-serif text-2xl font-semibold tracking-tight">
              Mesa · Hoy
            </h1>
            <p className="mt-1 text-sm text-muted-foreground">
              ¿Qué debo hacer hoy? — briefing operativo
              {account ? ` · ${account.name}` : ""}
            </p>
          </div>
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
        </div>

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
          </div>
        ) : null}

        <MesaLevelSection
          level={1}
          title="Qué ocurre"
          description="Mercado, riesgo, datos y sistema — sin ejecutar."
          testId="mesa-level-occurs"
        >
          <MesaOperationalHeaderStrip header={operationalHeader} />
          <MesaSessionStateCard session={sessionState} />
          <MesaDecisionAlertsPanel
            alerts={decisionAlerts}
            unifiedAlerts={unifiedAlerts}
          />
        </MesaLevelSection>

        <MesaLevelSection
          level={2}
          title="Qué debo hacer"
          description="Atención y posiciones — una acción principal, Confirm es la firma."
          testId="mesa-level-do"
        >
          <MesaAttentionQueue items={attentionItems} board={board} />
          <MesaPositionsSummary
            positions={positions}
            protectPlanByInstrument={protectPlanByInstrument}
            studiesByInstrument={studiesMap}
          />
        </MesaLevelSection>

        <MesaLevelSection
          level={3}
          title="Qué podría hacer"
          description="Oportunidades para ESTA cartera — no es un ranking del universo."
          testId="mesa-level-could"
        >
          <MesaCandidatesPanel
            groups={candidateGroups}
            entriesBlocked={entriesBlocked}
            portfolioRisk={portfolioRisk}
            sectorExposurePct={sectorExposurePct}
            sectorByInstrumentId={sectorByInstrumentId}
            positions={riskPositions}
            equity={portfolio?.totalEquity ?? null}
            cash={summaryQuery.data?.data?.cash ?? null}
          />
        </MesaLevelSection>

        <div
          className="rounded-md border border-border/60 bg-muted/20 px-4 py-3 text-sm"
          data-testid="mesa-system-health-link"
        >
          <p className="font-medium">Salud del sistema</p>
          <p className="mt-1 text-xs text-muted-foreground">
            OE-1, readiness, recon e incidentes históricos — auditoría
            read-only.
          </p>
          <Link
            to={mesaOperationalConsoleHref()}
            className="mt-2 inline-block text-xs text-primary hover:underline"
          >
            Abrir Consola operacional →
          </Link>
        </div>
      </div>
    </FeatureErrorBoundary>
  );
}
