/**
 * DÍA-D AUTO — ejecución manual desde la UI sobre la cola durable `auto_ops_jobs`.
 *
 * El botón NO ejecuta el motor en el navegador ni por HTTP síncrono: encola un job
 * `dia_d_replay` que el worker ejecuta como subproceso aislado. La UI observa el MISMO
 * job (estado, `progress` y `error`) y, al terminar, invalida el artefacto para que el
 * panel lo relea. Un fallo nunca borra el artefacto anterior: solo lo etiqueta.
 */

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AutoOpsJobV1 } from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

const ACTIVE_STATUSES = new Set(["queued", "running"]);
const POLL_MS = 1_500;

/**
 * Observa el job `dia_d_replay` de `(cuenta, día)`.
 *
 * **Continuidad durable:** al montar o cambiar de día/cuenta se limpia el job anterior y se
 * adopta el más reciente de `(cuenta, día)` si existe. Así un replay lanzado antes de
 * recargar (o desde otra pestaña) sigue mostrando estado/progreso en lugar de desaparecer, y
 * un job de otro contexto nunca se pinta aquí.
 */
export function useDiaDReplayJob(day: string | null) {
  const { effectiveAccountId } = useActiveAccount();
  const queryClient = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);
  const [settledJobId, setSettledJobId] = useState<string | null>(null);

  const latestQuery = useQuery({
    queryKey: ["auto-ops-jobs", effectiveAccountId, "dia_d_replay", day],
    queryFn: () =>
      api.listAutoOpsJobs({
        kind: "dia_d_replay",
        day: day as string,
        limit: 1,
      }),
    enabled: Boolean(effectiveAccountId && day),
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
      (await api.createAutoDiaDReplayJob({ day })) as unknown as AutoOpsJobV1,
    onSuccess: (job) => setJobId(job.id),
  });

  const job = (jobQuery.data as AutoOpsJobV1 | undefined) ?? null;

  // Cambio de contexto: se deja de observar el job anterior.
  useEffect(() => {
    setJobId(null);
    setSettledJobId(null);
  }, [day, effectiveAccountId]);

  // Rehidratación desde la cola durable (misma clave `(kind, cuenta, día)`).
  useEffect(() => {
    if (jobId !== null) return;
    const recent = latestQuery.data?.jobs?.[0] ?? null;
    if (!recent) return;
    setJobId(recent.id);
    if (!ACTIVE_STATUSES.has(recent.status)) setSettledJobId(recent.id);
  }, [jobId, latestQuery.data]);

  useEffect(() => {
    if (!job || jobId === null || jobId === settledJobId) return;
    if (ACTIVE_STATUSES.has(job.status)) return;
    // Terminal: se relee el artefacto (el bueno anterior o el recién escrito).
    setSettledJobId(jobId);
    void queryClient.invalidateQueries({
      queryKey: ["auto-dia-d-replay-days", effectiveAccountId],
    });
    // Se invalida el día DEL JOB, no el día que el usuario tenga ahora en pantalla.
    const jobDay = job.day ?? day;
    if (jobDay) {
      void queryClient.invalidateQueries({
        queryKey: ["auto-dia-d-replay", effectiveAccountId, jobDay],
      });
    }
    void queryClient.invalidateQueries({
      queryKey: ["auto-ops-jobs", effectiveAccountId],
    });
  }, [day, effectiveAccountId, job, jobId, queryClient, settledJobId]);

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
