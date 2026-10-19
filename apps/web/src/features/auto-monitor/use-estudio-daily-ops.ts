/**
 * AUTO · Operativa diaria por valor — hooks de lectura y de ejecución.
 *
 * El cálculo NO corre en el navegador ni en un request síncrono: la UI encola el job
 * `estudio_daily` (misma cola que el scheduler) y lee el parte durable que deja el worker.
 *
 * La validación estadística NO se recalcula aquí: se une en cliente con
 * `useAutoEstudioAudit()` por símbolo. La ventana PAPER global no se confunde con la
 * validación por valor.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AutoOpsJobV1 } from "@bolsa/shared";
import type { components } from "@/api/schema";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

type EstudioAuditDto = components["schemas"]["EstudioAuditDto"];
type EstudioAuditValueDto = components["schemas"]["EstudioAuditValueDto"];

const ACTIVE_STATUSES = new Set(["queued", "running"]);
const POLL_MS = 1_500;

export function estudioDailyQueryKey(
  accountId: string | null,
  asOf: string | null,
) {
  return ["auto-estudio-daily", accountId, asOf] as const;
}

export function useEstudioDailyOps(asOf: string | null) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery({
    queryKey: estudioDailyQueryKey(effectiveAccountId, asOf),
    queryFn: () => api.getAutoEstudioDaily(asOf ?? undefined),
    enabled: Boolean(effectiveAccountId && asOf),
    staleTime: 30_000,
    retry: false,
    // Sin `asOf` no se consulta; con él, el parte es durable y no necesita sondeo.
  });
}

/**
 * Encola «Calcular operativa diaria» y observa el MISMO job hasta su desenlace.
 *
 * **Continuidad durable:** el `jobId` no vive solo en memoria. Al montar (o al cambiar de
 * cuenta/día) se consulta el job más reciente de `(cuenta, día)` y, si existe, se observa:
 * un job `queued`/`running` lanzado antes de recargar o desde otra pestaña sigue mostrando
 * su progreso en vez de parecer que nunca se pidió.
 *
 * Al cambiar de día/cuenta se **limpia** el job observado: nunca se pinta el progreso ni el
 * error de un trabajo de otro contexto.
 */
export function useEstudioDailyJob(asOf: string | null) {
  const { effectiveAccountId } = useActiveAccount();
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [settledJobId, setSettledJobId] = useState<string | null>(null);

  // Job más reciente de (cuenta, día): fuente de rehidratación (el backend ya la expone).
  const latestQuery = useQuery({
    queryKey: ["auto-ops-jobs", effectiveAccountId, "estudio_daily", asOf],
    queryFn: () =>
      api.listAutoOpsJobs({
        kind: "estudio_daily",
        day: asOf as string,
        limit: 1,
      }),
    enabled: Boolean(effectiveAccountId && asOf),
    retry: false,
    staleTime: 5_000,
  });

  const jobQuery = useQuery({
    queryKey: ["auto-ops-job", effectiveAccountId, jobId],
    queryFn: async () =>
      (await api.getAutoOpsJob(jobId as string)) as unknown as AutoOpsJobV1,
    enabled: Boolean(jobId && effectiveAccountId),
    retry: false,
    refetchInterval: (query) => {
      const status = (query.state.data as AutoOpsJobV1 | undefined)?.status;
      return status && ACTIVE_STATUSES.has(status) ? POLL_MS : false;
    },
  });

  const mutation = useMutation({
    mutationFn: async () =>
      (await api.createAutoEstudioDailyJob({
        day: asOf,
      })) as unknown as AutoOpsJobV1,
    onSuccess: (job) => setJobId(job.id),
  });

  const job = (jobQuery.data as AutoOpsJobV1 | undefined) ?? null;

  // Cambio de contexto (día o cuenta): el job anterior deja de ser observable aquí.
  useEffect(() => {
    setJobId(null);
    setSettledJobId(null);
  }, [asOf, effectiveAccountId]);

  // Rehidratación: si no hay job local, se adopta el último job durable del (cuenta, día).
  useEffect(() => {
    if (jobId !== null) return;
    const recent = latestQuery.data?.jobs?.[0] ?? null;
    if (!recent) return;
    setJobId(recent.id);
    // Un job ya terminal no necesita re-invalidar el artefacto al rehidratarse.
    if (!ACTIVE_STATUSES.has(recent.status)) setSettledJobId(recent.id);
  }, [jobId, latestQuery.data]);

  useEffect(() => {
    if (!job || jobId === null || jobId === settledJobId) return;
    if (ACTIVE_STATUSES.has(job.status)) return;
    setSettledJobId(jobId);
    // Se invalida el día DEL JOB (no el día que el usuario tenga ahora en pantalla).
    void queryClient.invalidateQueries({
      queryKey: estudioDailyQueryKey(effectiveAccountId, job.day ?? asOf),
    });
    void queryClient.invalidateQueries({
      queryKey: ["auto-estudio-audit", effectiveAccountId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["auto-ops-jobs", effectiveAccountId],
    });
  }, [asOf, effectiveAccountId, job, jobId, queryClient, settledJobId]);

  return {
    job,
    hasAccount: Boolean(effectiveAccountId),
    isRunning: Boolean(job && ACTIVE_STATUSES.has(job.status)),
    isQueuing: mutation.isPending,
    runError: mutation.error,
    jobError: jobQuery.error,
    run: () => mutation.mutate(),
    reset: () => {
      setJobId(null);
      setSettledJobId(null);
      mutation.reset();
    },
  };
}

/**
 * Índice de la auditoría por símbolo (la clave del artefacto es el ticker; el parte diario
 * trae `symbol`). Un instrumento sin entrada en la auditoría NO se inventa: queda `null`.
 */
export function indexAuditValuesBySymbol(
  audit: EstudioAuditDto | null | undefined,
): Map<string, EstudioAuditValueDto> {
  const out = new Map<string, EstudioAuditValueDto>();
  for (const value of audit?.audit?.values ?? []) {
    const symbol = value.symbol?.trim().toUpperCase();
    if (symbol) out.set(symbol, value);
  }
  return out;
}

/**
 * Frase obligatoria cuando la evidencia histórica del valor **no** está causalmente ligada a
 * la señal del parte mostrado. Coincidir el ticker no es una atribución.
 */
export const AUDIT_NOT_ATTRIBUTED_LABEL =
  "Histórico del valor; no atribuido a esta señal";

/**
 * Frase cuando el ciclo declara la misma identidad estable (`planId`/`signalId`) que la señal.
 * Sin esa identidad no se afirma nada: el contrato actual de ciclos no la trae, así que el
 * resultado normal es «no atribuido».
 */
export const AUDIT_ATTRIBUTED_LABEL =
  "Vinculado por identidad (planId/signalId)";

type CycleIdentityLike = {
  planId?: string | null;
  signalId?: string | null;
};

export type AuditAttributionV1 = {
  attributed: boolean;
  label: string;
};

/**
 * Decide si un ciclo del audit está ligado a la señal por **identidad estable**.
 *
 * Solo un `planId` o `signalId` iguales atribuyen el ciclo. El símbolo, la fecha o el
 * `presetKey` **no** atribuyen: podrían ser evidencia histórica del mismo valor originada por
 * otra decisión. Un campo ausente nunca coincide.
 */
export function auditCycleAttribution(
  cycle: CycleIdentityLike,
  identity: { planId?: string | null; signalId?: string | null },
): AuditAttributionV1 {
  const planId = identity.planId?.trim();
  const signalId = identity.signalId?.trim();
  const cyclePlan = cycle.planId?.trim();
  const cycleSignal = cycle.signalId?.trim();
  const attributed =
    (Boolean(planId) && Boolean(cyclePlan) && planId === cyclePlan) ||
    (Boolean(signalId) && Boolean(cycleSignal) && signalId === cycleSignal);
  return {
    attributed,
    label: attributed ? AUDIT_ATTRIBUTED_LABEL : AUDIT_NOT_ATTRIBUTED_LABEL,
  };
}

/**
 * Atribución agregada de la evidencia mostrada bajo «Operación ejecutada».
 *
 * Solo se declara atribuida si **algún** ciclo comparte `planId`/`signalId`; en cualquier otro
 * caso (incluido contrato sin esos campos) se declara histórico no atribuido.
 */
export function auditAttributionForValue(
  cycles: readonly CycleIdentityLike[],
  identity: { planId?: string | null; signalId?: string | null },
): AuditAttributionV1 {
  const attributed = cycles.some(
    (cycle) => auditCycleAttribution(cycle, identity).attributed,
  );
  return {
    attributed,
    label: attributed ? AUDIT_ATTRIBUTED_LABEL : AUDIT_NOT_ATTRIBUTED_LABEL,
  };
}
