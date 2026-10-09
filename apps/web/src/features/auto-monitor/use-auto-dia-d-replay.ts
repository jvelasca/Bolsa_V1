/**
 * DÍA-D AUTO — hooks read-only del sandbox.
 *
 * El motor AUTO no se ejecuta por HTTP: el artefacto lo produce el CLI
 * (`v2_89_dia_d_auto_replay.py`) y estas queries solo lo **leen**. Los días disponibles se
 * consultan de forma perezosa (solo cuando el usuario abre la vista DÍA-D), de modo que el
 * monitor de la ventana actual no paga ninguna llamada extra.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

export function useAutoDiaDReplayDays(input?: { enabled?: boolean }) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery({
    queryKey: ["auto-dia-d-replay-days", effectiveAccountId],
    queryFn: () => api.getAutoDiaDReplayDays(),
    enabled: (input?.enabled ?? true) && Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}

export function useAutoDiaDReplay(
  day: string | null,
  input?: { enabled?: boolean },
) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery({
    queryKey: ["auto-dia-d-replay", effectiveAccountId, day],
    queryFn: () => api.getAutoDiaDReplay(day as string),
    enabled:
      (input?.enabled ?? true) && Boolean(day) && Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}
