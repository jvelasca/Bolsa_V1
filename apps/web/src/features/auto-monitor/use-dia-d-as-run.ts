/**
 * DÍA-D retrospectivo **as-run** (ADR-049) — hooks read-only + encolado del replay.
 *
 * El artefacto lo produce el CLI (`v2_102_dia_d_as_run.py`) dentro de un job de la cola
 * durable. La UI sólo lo lee: nunca reconstruye el estado ni rellena huecos.
 *
 * El contrato OpenAPI marca como opcionales los campos con default de FastAPI. Los
 * normalizadores los completan con el valor que el SERVIDOR ya garantiza (`[]`, `null`),
 * de modo que la vista trabaja con el DTO estricto y no repite `?? []` en cada render.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  DiaDAsRunArmV1,
  DiaDAsRunArtifactV1,
  DiaDAsRunListV1,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

type RawList = Awaited<ReturnType<typeof api.getAutoDiaDAsRunDays>>;
type RawArtifact = Awaited<ReturnType<typeof api.getAutoDiaDAsRun>>;

function toList(raw: RawList): DiaDAsRunListV1 {
  return {
    readOnly: raw.readOnly ?? true,
    days: raw.days ?? [],
    notes: raw.notes ?? [],
  };
}

function toArm(raw: NonNullable<RawArtifact["arms"]>[number]): DiaDAsRunArmV1 {
  return {
    arm: raw.arm,
    measured: raw.measured,
    reason: raw.reason ?? null,
    realizedR: raw.realizedR ?? null,
    pnlCurrency: raw.pnlCurrency ?? null,
    maeR: raw.maeR ?? null,
    mfeR: raw.mfeR ?? null,
    capture: raw.capture ?? null,
    returnPct: raw.returnPct ?? null,
    exits: raw.exits,
    stops: raw.stops,
    targets: raw.targets,
    legs: raw.legs,
    reasonCodes: raw.reasonCodes ?? [],
    decisions: (raw.decisions ?? []).map((decision) => {
      const row = decision as Record<string, unknown>;
      return {
        date: typeof row["date"] === "string" ? row["date"] : null,
        instrument: String(row["instrument"] ?? ""),
        action: String(row["action"] ?? ""),
        price: typeof row["price"] === "number" ? row["price"] : null,
        reason: String(row["reason"] ?? ""),
      };
    }),
  };
}

function toArtifact(raw: RawArtifact): DiaDAsRunArtifactV1 {
  const state = (raw.startingState ?? {}) as Record<string, unknown>;
  return {
    available: raw.available,
    readOnly: raw.readOnly ?? true,
    day: raw.day,
    status: raw.status ?? null,
    schemaVersion: raw.schemaVersion ?? null,
    costBps: raw.costBps ?? null,
    startingState: {
      legs: typeof state["legs"] === "number" ? state["legs"] : undefined,
      instruments: Array.isArray(state["instruments"])
        ? state["instruments"].map(String)
        : undefined,
      cashOnly:
        typeof state["cashOnly"] === "boolean" ? state["cashOnly"] : undefined,
    },
    arms: (raw.arms ?? []).map(toArm),
    gaps: (raw.gaps ?? []).map((gap) => ({
      arm: String(gap["arm"] ?? ""),
      reason: String(gap["reason"] ?? ""),
    })),
    hash: raw.hash ?? null,
    artifactModifiedAt: raw.artifactModifiedAt ?? null,
    meta: raw.meta ?? {},
    notes: raw.notes ?? [],
    // El servidor ya garantiza la forma; el normalizador solo evita `any` en la vista.
    audit: (raw.audit ?? null) as DiaDAsRunArtifactV1["audit"],
    certification: (raw.certification ??
      null) as DiaDAsRunArtifactV1["certification"],
  };
}

export function useAutoDiaDAsRunDays(input?: { enabled?: boolean }) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery<DiaDAsRunListV1>({
    queryKey: ["auto-dia-d-as-run-days", effectiveAccountId],
    queryFn: async () => toList(await api.getAutoDiaDAsRunDays()),
    enabled: (input?.enabled ?? true) && Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}

export function useAutoDiaDAsRun(
  day: string | null,
  input?: { enabled?: boolean },
) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery<DiaDAsRunArtifactV1>({
    queryKey: ["auto-dia-d-as-run", effectiveAccountId, day],
    queryFn: async () => toArtifact(await api.getAutoDiaDAsRun(day as string)),
    enabled:
      (input?.enabled ?? true) && Boolean(day) && Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}

/**
 * Encola el replay as-run del día. Idempotente por `(kind, cuenta, día)` en el servidor:
 * reencolar mientras hay un job activo devuelve ESE job (`created=false`), no duplica.
 */
export function useEnqueueDiaDAsRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input?: {
      day?: string | null;
      to?: string | null;
      costBps?: number | null;
    }) => api.createAutoDiaDAsRunJob(input),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["auto-dia-d-as-run-days"],
      });
    },
  });
}
