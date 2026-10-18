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

/** Encola «Calcular operativa diaria» y observa el MISMO job hasta su desenlace. */
export function useEstudioDailyJob(asOf: string | null) {
  const { effectiveAccountId } = useActiveAccount();
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [settledJobId, setSettledJobId] = useState<string | null>(null);

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

  useEffect(() => {
    if (!job || jobId === null || jobId === settledJobId) return;
    if (ACTIVE_STATUSES.has(job.status)) return;
    setSettledJobId(jobId);
    void queryClient.invalidateQueries({
      queryKey: estudioDailyQueryKey(effectiveAccountId, asOf),
    });
    void queryClient.invalidateQueries({
      queryKey: ["auto-estudio-audit", effectiveAccountId],
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
