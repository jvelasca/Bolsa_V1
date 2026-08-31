import { useQuery } from "@tanstack/react-query";
import type { SubmitIntentListItemV1 } from "@bolsa/shared";
import { api } from "@/lib/api";

export function useInFlightSubmitIntents(accountId: string | null | undefined) {
  return useQuery({
    queryKey: ["submit-intents-in-flight", accountId],
    queryFn: () => api.getSubmitIntents(accountId!),
    enabled: Boolean(accountId),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}

/**
 * Lookup by soft-joined instrumentId. Prefer crash-signal phases
 * (send_attempted / venue_bound) over pure recorded.
 */
export function pickSubmitIntentForInstrument(
  intents: SubmitIntentListItemV1[] | undefined | null,
  instrumentId: string | null | undefined,
): SubmitIntentListItemV1 | null {
  const iid = (instrumentId ?? "").trim();
  if (!iid || !intents?.length) return null;
  const matches = intents.filter(
    (item) => (item.instrumentId ?? "").trim() === iid,
  );
  if (matches.length === 0) return null;
  const crash = matches.find(
    (item) => item.phase === "send_attempted" || item.phase === "venue_bound",
  );
  return crash ?? matches[0] ?? null;
}
