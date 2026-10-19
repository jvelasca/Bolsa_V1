/**
 * DÍA-D del VALOR — ejecución bajo demanda sobre la cola durable `auto_ops_jobs`.
 *
 * El botón NO ejecuta el motor en el navegador: encola un job `dia_d_value_replay` con
 * `payload.symbol`. El worker lanza el MISMO CLI con `--watch <símbolo>` y escribe un
 * artefacto PROPIO (`…/<cuenta>/values/<SÍMBOLO>/dia-d-auto-<D>.json`); el artefacto del día
 * completo no se toca.
 *
 * Rehidratación acotada al valor: se adopta el job del día **cuyo `payload.symbol` coincide**;
 * el job de otro símbolo no se pinta aquí. El índice único parcial serializa por
 * `(kind, cuenta, día)`: si al encolar vuelve un job de otro símbolo, la UI lo DECLARA
 * (`occupiedBy`) en vez de fingir que encoló el suyo.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AutoOpsJobV1 } from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

const ACTIVE_STATUSES = new Set(["queued", "running"]);
const POLL_MS = 1_500;
const LIST_LIMIT = 50;

export function diaDValueReplayQueryKey(
  accountId: string | null,
  day: string | null,
  symbol: string | null,
) {
  return ["auto-dia-d-replay-value", accountId, day, symbol] as const;
}

function jobSymbol(
  job: { payload?: Record<string, unknown> | null } | null | undefined,
): string | null {
  const raw = job?.payload?.symbol;
  const text = typeof raw === "string" ? raw.trim().toUpperCase() : "";
  return text || null;
}

export function useDiaDValueReplayJob(
  day: string | null,
  symbol: string | null,
) {
  const { effectiveAccountId } = useActiveAccount();
  const queryClient = useQueryClient();
  const wanted = symbol?.trim().toUpperCase() ?? null;
  const [jobId, setJobId] = useState<string | null>(null);
  const [settledJobId, setSettledJobId] = useState<string | null>(null);
  const [occupiedBy, setOccupiedBy] = useState<string | null>(null);

  // Jobs del (cuenta, día): se filtra por `payload.symbol` en cliente. La lista es corta
  // (kinds distintos por día) y evita inventar un índice por símbolo que el backend no tiene.
  const latestQuery = useQuery({
    queryKey: ["auto-ops-jobs", effectiveAccountId, "dia_d_value_replay", day],
    queryFn: () =>
      api.listAutoOpsJobs({
        kind: "dia_d_value_replay",
        day: day as string,
        limit: LIST_LIMIT,
      }),
    enabled: Boolean(effectiveAccountId && day && wanted),
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
      (await api.createAutoDiaDValueReplayJob({
        day,
        symbol: wanted as string,
      })) as unknown as AutoOpsJobV1,
    onSuccess: (job) => {
      const recent = jobSymbol(job);
      if (recent && recent !== wanted) {
        // El hueco (kind, cuenta, día) está ocupado por otro valor: se declara, no se pinta.
        setOccupiedBy(recent);
        return;
      }
      setOccupiedBy(null);
      setJobId(job.id);
    },
  });

  const job = (jobQuery.data as AutoOpsJobV1 | undefined) ?? null;

  // Cambio de cuenta/día/símbolo: el job anterior deja de ser observable aquí.
  useEffect(() => {
    setJobId(null);
    setSettledJobId(null);
    setOccupiedBy(null);
  }, [day, wanted, effectiveAccountId]);

  // Rehidratación acotada: solo el job del MISMO símbolo, y solo si sigue visible.
  useEffect(() => {
    if (jobId !== null) return;
    const recent = latestQuery.data?.jobs?.[0] ?? null;
    if (!recent || jobSymbol(recent) !== wanted) return;
    setJobId(recent.id);
    if (!ACTIVE_STATUSES.has(recent.status)) setSettledJobId(recent.id);
  }, [jobId, latestQuery.data, wanted]);

  useEffect(() => {
    if (!job || jobId === null || jobId === settledJobId) return;
    if (ACTIVE_STATUSES.has(job.status)) return;
    setSettledJobId(jobId);
    void queryClient.invalidateQueries({
      queryKey: diaDValueReplayQueryKey(
        effectiveAccountId,
        job.day ?? day,
        wanted,
      ),
    });
    // La cadena también se relee: su bloque DÍA-D declara el eslabón recién verificado.
    void queryClient.invalidateQueries({
      queryKey: ["auto-estudio-chain", effectiveAccountId],
    });
    void queryClient.invalidateQueries({
      queryKey: ["auto-ops-jobs", effectiveAccountId],
    });
  }, [day, effectiveAccountId, job, jobId, queryClient, settledJobId, wanted]);

  return {
    job,
    hasAccount: Boolean(effectiveAccountId),
    isRunning: Boolean(job && ACTIVE_STATUSES.has(job.status)),
    isQueuing: mutation.isPending,
    /** Símbolo del job ACTIVO del día cuando es OTRO valor (limitación declarada). */
    occupiedBy,
    runError: mutation.error,
    jobError: jobQuery.error,
    run: () => {
      // Fail-closed en el cliente: sin cuenta, día o símbolo no se encola nada.
      if (!effectiveAccountId || !wanted || !day) return;
      mutation.mutate();
    },
    reset: () => {
      setJobId(null);
      setSettledJobId(null);
      setOccupiedBy(null);
      mutation.reset();
    },
  };
}
