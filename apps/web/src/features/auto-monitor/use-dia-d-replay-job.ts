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

export function useDiaDReplayJob(day: string | null) {
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
      (await api.createAutoDiaDReplayJob({ day })) as unknown as AutoOpsJobV1,
    onSuccess: (job) => setJobId(job.id),
  });

  const job = (jobQuery.data as AutoOpsJobV1 | undefined) ?? null;

  useEffect(() => {
    if (!job || jobId === null || jobId === settledJobId) return;
    if (ACTIVE_STATUSES.has(job.status)) return;
    // Terminal: se relee el artefacto (el bueno anterior o el recién escrito).
    setSettledJobId(jobId);
    void queryClient.invalidateQueries({
      queryKey: ["auto-dia-d-replay-days", effectiveAccountId],
    });
    if (day) {
      void queryClient.invalidateQueries({
        queryKey: ["auto-dia-d-replay", effectiveAccountId, day],
      });
    }
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
