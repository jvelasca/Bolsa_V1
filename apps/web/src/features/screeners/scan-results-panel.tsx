import { useMutation } from "@tanstack/react-query";
import { Bell, BrainCircuit, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import { useScreenerPreferencesStore } from "@/stores/screener-preferences-store";
import {
  type ExecutionActionResultDto,
  type ExecutionPolicySummaryDto,
  type ScanRunResultDto,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import type { ScanRunnerConfig as LocalScanConfig } from "@/features/screeners/scan-runner-form";
import { ScanResultsTable } from "@/features/screeners/scan-results-table";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useAlertsStore } from "@/stores/alerts-store";
import { useTrackerAlarmInboxStore } from "@/stores/tracker-alarm-inbox-store";
import {
  formatAlarmRouteSummary,
  formatScanHitAlarmToast,
  isAlarmSafeMode,
} from "@/features/screeners/tracker-alarms";
import {
  openHelpAiPlatform,
  type SupervisedProposePayload,
  useSupervisedF3QueueStore,
} from "@/stores/supervised-f3-queue-store";

interface ScanResultsPanelProps {
  result: ScanRunResultDto;
  scanConfig: LocalScanConfig;
  showSkipped?: boolean;
  full?: boolean;
  executionPolicies?: ExecutionPolicySummaryDto[];
  scanJobId?: string | null;
  defaultPolicyId?: string | null;
}

const ACTION_LABELS: Record<string, string> = {
  inform_only: "Informado",
  alert_dispatched: "Alerta enviada",
  trade_executed: "Trade demo",
  skipped: "Omitido",
};

const F3_TOP_N = 5;

export function ScanResultsPanel({
  result,
  scanConfig,
  showSkipped = true,
  full = false,
  executionPolicies = [],
  scanJobId = null,
  defaultPolicyId = null,
}: ScanResultsPanelProps) {
  const pushToast = useAlertsStore((s) => s.pushToast);
  const pushInboxFromScan = useTrackerAlarmInboxStore((s) => s.pushFromScan);
  const { effectiveAccountId } = useActiveAccount();
  const enqueueMany = useSupervisedF3QueueStore((s) => s.enqueueMany);
  const lastExecutionPolicyId = useScreenerPreferencesStore(
    (state) => state.lastExecutionPolicyId,
  );
  const setLastExecutionPolicyId = useScreenerPreferencesStore(
    (state) => state.setLastExecutionPolicyId,
  );
  const preferredPolicyId =
    defaultPolicyId ?? lastExecutionPolicyId ?? executionPolicies[0]?.id ?? "";
  const [selectedPolicyId, setSelectedPolicyId] = useState(preferredPolicyId);
  const [lastActions, setLastActions] = useState<ExecutionActionResultDto[]>(
    [],
  );
  const [alertFeedback, setAlertFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);
  const [f3Feedback, setF3Feedback] = useState<string | null>(null);
  const alarmedScanIdRef = useRef<string | null>(null);

  useEffect(() => {
    const next =
      defaultPolicyId ??
      lastExecutionPolicyId ??
      executionPolicies[0]?.id ??
      "";
    if (next) setSelectedPolicyId(next);
  }, [defaultPolicyId, lastExecutionPolicyId, executionPolicies]);

  /** Toasts B1 + inbox Trading (cuenta activa DEMO) cuando hay alarmRoute. */
  useEffect(() => {
    if (!result.scanId || alarmedScanIdRef.current === result.scanId) return;
    const route = result.alarmRoute;
    if (
      route &&
      isAlarmSafeMode(route.mode) &&
      (route.actions?.length ?? 0) > 0
    ) {
      alarmedScanIdRef.current = result.scanId;
      if (effectiveAccountId) {
        pushInboxFromScan(result, effectiveAccountId, {
          listId: scanConfig.listId || result.listId || null,
        });
      }
      pushToast(formatAlarmRouteSummary(route));
      for (const hit of result.hits.slice(0, 8)) {
        pushToast(formatScanHitAlarmToast(hit));
      }
    }
  }, [
    result,
    result.scanId,
    result.alarmRoute,
    result.hits,
    pushToast,
    pushInboxFromScan,
    effectiveAccountId,
    scanConfig.listId,
  ]);

  const executeMutation = useMutation({
    mutationFn: async () => {
      if (!selectedPolicyId)
        throw new Error("Selecciona una política de ejecución");
      if (scanJobId) {
        return api.executeScanJobHits(scanJobId, {
          policyId: selectedPolicyId,
        });
      }
      return api.routeSignalsThroughPolicy(selectedPolicyId, {
        hits: result.hits,
      });
    },
    onSuccess: (response) => {
      setLastActions(response.data.actions);
      const mode = response.data.mode;
      if (isAlarmSafeMode(mode)) {
        const withRoute: ScanRunResultDto = {
          ...result,
          alarmRoute: {
            policyId: response.data.policyId,
            mode,
            actions: response.data.actions,
          },
        };
        if (effectiveAccountId) {
          pushInboxFromScan(withRoute, effectiveAccountId, {
            listId: scanConfig.listId || result.listId || null,
          });
        }
        pushToast(
          formatAlarmRouteSummary({
            policyId: response.data.policyId,
            mode,
            actions: response.data.actions,
          }),
        );
        for (const hit of result.hits.slice(0, 8)) {
          pushToast(formatScanHitAlarmToast(hit));
        }
      }
    },
  });

  const enqueueF3Mutation = useMutation({
    mutationFn: async () => {
      if (!effectiveAccountId) throw new Error("Selecciona una cuenta activa");
      const hits = result.hits.slice(0, F3_TOP_N);
      if (!hits.length) throw new Error("Sin coincidencias");
      const strategyRef =
        result.strategyDefinitionId ??
        hits[0]?.signal.strategyDefinitionId ??
        undefined;
      const payloads: SupervisedProposePayload[] = [];
      const errors: string[] = [];
      for (const hit of hits) {
        try {
          const res = await api.proposeRecommendation({
            instrumentId: hit.instrumentId,
            symbol: hit.symbol,
            accountId: effectiveAccountId,
            suggestedQuantity: 1,
            includeFundamentals: true,
            includeEvidence: true,
            includeNews: true,
            strategyOrSignalRef: strategyRef ?? hit.signal.strategyDefinitionId,
          });
          payloads.push(res.data as SupervisedProposePayload);
        } catch (e) {
          errors.push(`${hit.symbol}: ${(e as Error).message}`);
        }
      }
      return { payloads, errors };
    },
    onSuccess: ({ payloads, errors }) => {
      const n = enqueueMany(payloads, {
        scanId: result.scanId,
        origin: "scan",
      });
      setF3Feedback(
        `Encoladas ${n} propuestas F3` +
          (errors.length ? ` · ${errors.length} error(es)` : "") +
          " — revisa Ayuda → Plataforma IA · Supervisado F3",
      );
      if (n > 0) openHelpAiPlatform({ panel: "supervised-f3" });
    },
    onError: (e: Error) => setF3Feedback(e.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
        <p className="text-muted-foreground">
          Rastreo{" "}
          <span className="font-mono text-xs">
            {result.scanId.slice(0, 8)}…
          </span>{" "}
          · <strong className="text-foreground">{result.hitCount}</strong>{" "}
          coincidencias / {result.scannedCount} escaneados
          {result.skipped.length > 0 && ` · ${result.skipped.length} omitidos`}
          {result.scanMode === "hybrid" && " · modo híbrido"}
          {result.scorerVersion && ` · scorer ${result.scorerVersion}`}
          {result.fundamentalsRefreshedCount != null &&
            result.fundamentalsRefreshedCount > 0 &&
            ` · ${result.fundamentalsRefreshedCount} fundamentales refrescados`}
        </p>
        {full && (
          <Link
            to="/alerts"
            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
          >
            <Bell className="h-3.5 w-3.5" />
            Alertas SC-3
          </Link>
        )}
      </div>

      {result.hits.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-dashed border-primary/30 bg-primary/5 p-3">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={enqueueF3Mutation.isPending || !effectiveAccountId}
            onClick={() => enqueueF3Mutation.mutate()}
          >
            <BrainCircuit className="mr-1 h-3.5 w-3.5" />
            {enqueueF3Mutation.isPending
              ? "Proponiendo…"
              : `Encolar F3 (top ${Math.min(F3_TOP_N, result.hits.length)})`}
          </Button>
          <button
            type="button"
            className="text-xs text-primary hover:underline"
            onClick={() => openHelpAiPlatform({ panel: "supervised-f3" })}
          >
            Abrir cola en Ayuda → Plataforma IA
          </button>
          {!effectiveAccountId ? (
            <span className="text-[11px] text-muted-foreground">
              Necesitas cuenta activa
            </span>
          ) : null}
        </div>
      )}

      {f3Feedback ? (
        <p className="text-xs text-foreground/80">{f3Feedback}</p>
      ) : null}

      {full && result.hits.length > 0 && executionPolicies.length > 0 && (
        <div className="flex flex-wrap items-end gap-2 rounded-lg border border-border bg-muted/20 p-3">
          <label className="text-sm">
            Política de ejecución
            <select
              value={selectedPolicyId}
              onChange={(e) => {
                const id = e.target.value;
                setSelectedPolicyId(id);
                setLastExecutionPolicyId(id || null);
              }}
              className="mt-1 block min-w-[200px] rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="">Selecciona…</option>
              {executionPolicies.map((policy) => (
                <option key={policy.id} value={policy.id}>
                  {policy.name} ({policy.mode})
                </option>
              ))}
            </select>
          </label>
          <Button
            type="button"
            size="sm"
            disabled={!selectedPolicyId || executeMutation.isPending}
            onClick={() => executeMutation.mutate()}
          >
            <Zap className="mr-1 h-3.5 w-3.5" />
            {executeMutation.isPending
              ? "Ejecutando…"
              : "Ejecutar política en coincidencias"}
          </Button>
        </div>
      )}

      {executeMutation.isError && (
        <p className="text-xs text-destructive">
          {(executeMutation.error as Error).message}
        </p>
      )}

      {lastActions.length > 0 && (
        <ul className="space-y-1 text-xs text-muted-foreground">
          {lastActions.map((action, index) => (
            <li key={`${action.instrumentId}-${index}`}>
              {action.instrumentId.slice(0, 8)}… · {action.signalKind} →{" "}
              <span className="text-foreground">
                {ACTION_LABELS[action.status] ?? action.status}
              </span>
              {action.reason && ` (${action.reason})`}
            </li>
          ))}
        </ul>
      )}

      {result.hits.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Sin señales en la última barra de la lista.
        </p>
      ) : (
        <ScanResultsTable
          result={result}
          scanConfig={scanConfig}
          full={full}
          onSubscribeSuccess={() =>
            setAlertFeedback({
              type: "success",
              message: "Alerta creada — ver /alerts",
            })
          }
          onSubscribeError={(message) =>
            setAlertFeedback({ type: "error", message })
          }
        />
      )}

      {showSkipped && result.skipped.length > 0 && (
        <details className="text-xs text-muted-foreground">
          <summary className="cursor-pointer font-medium">
            {result.skipped.length} instrumentos omitidos
          </summary>
          <ul className="mt-2 max-h-32 space-y-1 overflow-y-auto">
            {result.skipped.map((item) => (
              <li key={item.instrumentId}>
                <span className="font-mono">
                  {item.instrumentId.slice(0, 8)}…
                </span>{" "}
                — {item.reason}
              </li>
            ))}
          </ul>
        </details>
      )}

      {alertFeedback?.type === "success" && (
        <p className="text-xs text-emerald-600">{alertFeedback.message}</p>
      )}
      {alertFeedback?.type === "error" && (
        <p className="text-xs text-destructive">{alertFeedback.message}</p>
      )}
    </div>
  );
}
