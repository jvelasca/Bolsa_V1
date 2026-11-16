/**
 * Verificación periódica de estrategia (ADR-050) — hooks read-only + recálculo advisory.
 *
 * El veredicto se calcula sobre **épocas no solapadas**: la ventana móvil (`rolling`) es
 * historial visual y nunca certifica. `activationAllowed` es siempre `false`: nada de lo que
 * se lea o se dispare aquí autoriza a operar.
 *
 * El recálculo (`POST`) sella el run en el índice durable; si la época ya está sellada con
 * otra medición el servidor responde `409` y aquí se declara, no se reintenta a ciegas.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
  StrategyVerificationHistoryDto,
  StrategyVerificationKind,
  StrategyVerificationLedgerDto,
  StrategyVerificationOverviewDto,
  StrategyVerificationProfileResponseDto,
  StrategyVerificationRecomputeResponseDto,
  StrategyVerificationRunDto,
  StrategyVerificationVerdictDto,
} from "@bolsa/shared";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

type RawRun = NonNullable<
  Awaited<ReturnType<typeof api.getAutoStrategyVerification>>["runs"]
>[number];

function toRun(raw: RawRun): StrategyVerificationRunDto {
  return {
    id: raw.id,
    accountId: raw.accountId,
    profileId: raw.profileId,
    profileHash: raw.profileHash,
    kind: raw.kind as StrategyVerificationKind,
    day: raw.day,
    toDay: raw.toDay,
    measurementHash: raw.measurementHash,
    verdict: raw.verdict as StrategyVerificationRunDto["verdict"],
    strategyVersion: raw.strategyVersion ?? null,
    payload: raw.payload ?? {},
    createdAt: raw.createdAt,
  };
}

function toOverview(
  raw: Awaited<ReturnType<typeof api.getAutoStrategyVerification>>,
): StrategyVerificationOverviewDto {
  return {
    available: raw.available,
    activationAllowed: false,
    latest: raw.latest ? toRun(raw.latest) : null,
    runs: (raw.runs ?? []).map(toRun),
    notes: raw.notes ?? [],
  };
}

/**
 * El veredicto se guarda en `payload`; la UI lo lee con forma tipada. No se re-deriva: el
 * servidor es la única fuente de verdad del cálculo.
 */
export function verdictOf(
  run: StrategyVerificationRunDto | null,
): StrategyVerificationVerdictDto | null {
  if (!run) return null;
  const payload = run.payload as Partial<StrategyVerificationVerdictDto>;
  if (typeof payload.verdict !== "string") return null;
  return {
    ...(payload as StrategyVerificationVerdictDto),
    activationAllowed: false,
  };
}

export function useStrategyVerificationProfile(input?: { enabled?: boolean }) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery<StrategyVerificationProfileResponseDto>({
    queryKey: ["auto-strategy-verification-profile", effectiveAccountId],
    queryFn: async () => {
      const raw = await api.getAutoStrategyVerificationProfile();
      return {
        available: raw.available,
        activationAllowed: false,
        profile: raw.profile
          ? (raw.profile as StrategyVerificationProfileResponseDto["profile"])
          : undefined,
        profileHash: raw.profileHash ?? undefined,
        notes: raw.notes ?? [],
      };
    },
    enabled: (input?.enabled ?? true) && Boolean(effectiveAccountId),
    staleTime: 60_000,
    retry: false,
  });
}

export function useStrategyVerification(input?: { enabled?: boolean }) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery<StrategyVerificationOverviewDto>({
    queryKey: ["auto-strategy-verification", effectiveAccountId],
    queryFn: async () => toOverview(await api.getAutoStrategyVerification()),
    enabled: (input?.enabled ?? true) && Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}

export function useStrategyVerificationHistory(input?: {
  kind?: StrategyVerificationKind;
  limit?: number;
  enabled?: boolean;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const kind = input?.kind ?? "epoch";
  return useQuery<StrategyVerificationHistoryDto>({
    queryKey: ["auto-strategy-verification-history", effectiveAccountId, kind],
    queryFn: async () => {
      const raw = await api.getAutoStrategyVerificationHistory({
        kind,
        limit: input?.limit,
      });
      return {
        available: raw.available,
        activationAllowed: false,
        kind: raw.kind as StrategyVerificationKind,
        runs: (raw.runs ?? []).map(toRun),
        notes: raw.notes ?? [],
      };
    },
    enabled: (input?.enabled ?? true) && Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}

export function useStrategyVerificationLedger(input: {
  day: string | null;
  arm?: string;
  instrument?: string;
  outcome?: string;
  quality?: string;
  enabled?: boolean;
}) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery<StrategyVerificationLedgerDto>({
    queryKey: [
      "auto-strategy-verification-ledger",
      effectiveAccountId,
      input.day,
      input.arm ?? null,
      input.instrument ?? null,
      input.outcome ?? null,
      input.quality ?? null,
    ],
    queryFn: async () => {
      const raw = await api.getAutoStrategyVerificationLedger({
        day: input.day as string,
        arm: input.arm,
        instrument: input.instrument,
        outcome: input.outcome,
        quality: input.quality,
      });
      return {
        available: raw.available,
        activationAllowed: false,
        day: raw.day,
        rows: (raw.rows ??
          []) as unknown as StrategyVerificationLedgerDto["rows"],
        notes: raw.notes ?? [],
      };
    },
    enabled:
      (input.enabled ?? true) &&
      Boolean(input.day) &&
      Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}

/**
 * Recalcula y sella el veredicto. Un `409` significa «hueco declarado o época ya sellada con
 * otra medición»: se muestra tal cual, no se insiste.
 */
export function useRecomputeStrategyVerification() {
  const queryClient = useQueryClient();
  return useMutation<
    StrategyVerificationRecomputeResponseDto,
    Error,
    | {
        everyDays?: number;
        anchorDay?: string;
        healthState?: string;
        limitDays?: number;
      }
    | undefined
  >({
    mutationFn: async (input) => {
      const raw = await api.recomputeAutoStrategyVerification({
        everyDays: input?.everyDays,
        anchorDay: input?.anchorDay,
        healthState: input?.healthState,
        limitDays: input?.limitDays ?? 48,
      });
      return {
        available: raw.available,
        activationAllowed: false,
        run: toRun(raw.run),
        verdict: {
          ...(raw.verdict as StrategyVerificationVerdictDto),
          activationAllowed: false,
        },
      };
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["auto-strategy-verification"],
      });
      void queryClient.invalidateQueries({
        queryKey: ["auto-strategy-verification-history"],
      });
    },
  });
}
