/**
 * DÍA-D AUTO · FEEDBACK — hooks read-only de la ventana por valor.
 *
 * El motor AUTO no se ejecuta por HTTP: el artefacto lo produce el CLI
 * (`v2_90_dia_d_feedback.py`) y estas queries solo lo **leen**. Las ventanas disponibles y el
 * artefacto más reciente se consultan de forma perezosa (solo cuando el usuario abre la
 * sub-vista "Feedback por valor"), de modo que el monitor de la ventana actual no paga ninguna
 * llamada extra.
 */

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

export function useAutoDiaDFeedbackList(input?: { enabled?: boolean }) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery({
    queryKey: ["auto-dia-d-feedback-list", effectiveAccountId],
    queryFn: () => api.getAutoDiaDFeedbackList(),
    enabled: (input?.enabled ?? true) && Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}

export function useAutoDiaDFeedback(window: string | null) {
  const { effectiveAccountId } = useActiveAccount();
  return useQuery({
    queryKey: ["auto-dia-d-feedback", effectiveAccountId, window],
    queryFn: () => api.getAutoDiaDFeedback(window as string),
    enabled: Boolean(window) && Boolean(effectiveAccountId),
    staleTime: 30_000,
    retry: false,
  });
}
