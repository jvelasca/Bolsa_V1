/**
 * Mesa · Hoy — home operativa diaria (ADR-037).
 * Orden invariante: incidentes → sesión → KPIs → atención → posiciones → candidatos → salud.
 */

import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import type { ProtectPlanV1 } from "@bolsa/shared";
import {
  buildMesaActionQueue,
  buildMesaCandidateGroups,
  buildMesaSessionState,
  filterMesaAttentionItems,
  mesaEntriesBlocked,
  studiesByInstrumentMap,
} from "@bolsa/shared";
import { Button } from "@/components/ui/button";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { MesaIncidentBanner } from "@/features/operations/mesa-incident-banner";
import {
  portfolioReconStatusFromReport,
  useOpsSelfEval,
} from "@/features/operational-console/use-ops-self-eval";
import { MesaDailyHeader } from "@/features/mesa/mesa-daily-header";
import { MesaSessionStateCard } from "@/features/mesa/mesa-session-state-card";
import { MesaAttentionQueue } from "@/features/mesa/mesa-attention-queue";
import { MesaPositionsSummary } from "@/features/mesa/mesa-positions-summary";
import { MesaCandidatesPanel } from "@/features/mesa/mesa-candidates-panel";
import { mesaOperationalConsoleHref } from "@/features/mesa/mesa-nav-links";
import { api } from "@/lib/api";
import { useActiveAccountQueryKey } from "@/stores/active-account-store";

const STUDIES_LIMIT = 200;

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
    refetchInterval: 60_000,
  });

  const portfolioQuery = useQuery({
    queryKey: ["portfolio", accountScope],
    queryFn: api.getPortfolio,
    staleTime: 15_000,
  });

  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: () => api.getAccountSummary(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });

  const killQuery = useQuery({
    queryKey: ["risk-kill-switch"],
    queryFn: () => api.getRiskKillSwitch(),
    staleTime: 15_000,
  });

  const studiesQuery = useQuery({
    queryKey: ["decision-studies", effectiveAccountId, "mesa"],
    queryFn: () =>
      api.getDecisionStudies(effectiveAccountId!, { limit: STUDIES_LIMIT }),
    enabled: Boolean(effectiveAccountId),
    staleTime: 30_000,
  });

  const board = boardQuery.data?.data;
  const portfolio = portfolioQuery.data?.data;
  const studies = useMemo(
    () => studiesQuery.data?.data?.studies ?? [],
    [studiesQuery.data],
  );
  const studiesMap = useMemo(() => studiesByInstrumentMap(studies), [studies]);

  const killOn = killQuery.data?.effective === true;
  const vetoed = board?.buckets?.vetoed ?? 0;
  const incidentsQuery = useQuery({
    queryKey: ["operational-incidents-active", effectiveAccountId],
    queryFn: () => api.getActiveOperationalIncidents(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });
  const incidentCount = incidentsQuery.data?.data?.incidents?.length ?? 0;

  const entriesBlocked = mesaEntriesBlocked({
    killSwitchEffective: killOn,
    incidents: incidentsQuery.data?.data?.incidents,
    vetoed,
  });

  const sessionState = useMemo(
    () =>
      buildMesaSessionState(board, {
        entriesBlocked,
        killSwitchEffective: killOn,
        incidentCount,
      }),
    [board, entriesBlocked, killOn, incidentCount],
  );

  const attentionItems = useMemo(() => {
    const queue = buildMesaActionQueue(board);
    return filterMesaAttentionItems(queue);
  }, [board]);

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

  const positions = portfolio?.positions ?? [];
  const alertCount =
    attentionItems.length + (board?.buckets?.pendingConfirm ?? 0);

  const isRefreshing =
    boardQuery.isFetching ||
    portfolioQuery.isFetching ||
    studiesQuery.isFetching;

  function refreshAll() {
    void boardQuery.refetch();
    void portfolioQuery.refetch();
    void studiesQuery.refetch();
    void selfEvalQuery.refetch();
  }

  return (
    <div
      className="mx-auto max-w-5xl space-y-6 p-4 sm:p-6"
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

      {effectiveAccountId && incidentCount > 0 ? (
        <div data-testid="mesa-incident-section">
          <MesaIncidentBanner
            accountId={effectiveAccountId}
            portfolioReconStatus={portfolioReconStatus}
            className="border-rose-500/50 bg-rose-500/10"
          />
          <p className="mt-2 text-xs font-medium text-rose-700 dark:text-rose-300">
            Nuevas entradas: BLOQUEADAS · Automatismos: BLOQUEADOS · Desriesgo
            humano: DISPONIBLE
          </p>
        </div>
      ) : null}

      <MesaSessionStateCard session={sessionState} />

      <MesaDailyHeader
        cash={summaryQuery.data?.data?.cash ?? null}
        equity={portfolio?.totalEquity ?? null}
        unrealizedPnl={portfolio?.totalUnrealizedPnl ?? null}
        positionsCount={positions.length}
        alertCount={alertCount}
        criticalAlerts={incidentCount}
      />

      <MesaAttentionQueue items={attentionItems} board={board} />

      <MesaPositionsSummary
        positions={positions}
        protectPlanByInstrument={protectPlanByInstrument}
        studiesByInstrument={studiesMap}
      />

      <MesaCandidatesPanel
        groups={candidateGroups}
        entriesBlocked={entriesBlocked}
      />

      <div
        className="rounded-md border border-border/60 bg-muted/20 px-4 py-3 text-sm"
        data-testid="mesa-system-health-link"
      >
        <p className="font-medium">Salud del sistema</p>
        <p className="mt-1 text-xs text-muted-foreground">
          OE-1, readiness, recon e incidentes históricos — auditoría read-only.
        </p>
        <Link
          to={mesaOperationalConsoleHref()}
          className="mt-2 inline-block text-xs text-primary hover:underline"
        >
          Abrir Consola operacional →
        </Link>
      </div>
    </div>
  );
}
