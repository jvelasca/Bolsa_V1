/**
 * PAPER-2 — hook de lectura read-only de la evidencia durable PAPER.
 *
 * Una sola query sobre el DTO canónico; el mapeo puro (`paper-evidence-from-dto.ts`) traduce a los
 * hechos del contrato y `buildPaperConfirmationVerdict` produce el veredicto reservado. La UI no
 * re-deriva cifras ni emite confirmación.
 */

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { type PaperConfirmationVerdictV1 } from "./paper-confirmation-contract";
import { buildPaperEvidenceVerdictFromDto } from "./paper-evidence-from-dto";

export function useAutoPaperEvidence(input?: {
  strategyVersion?: string[];
  enabled?: boolean;
}) {
  const { effectiveAccountId } = useActiveAccount();
  const strategyVersion = input?.strategyVersion ?? [];
  const hasVersions = strategyVersion.length > 0;

  const query = useQuery({
    queryKey: [
      "auto-paper-evidence",
      effectiveAccountId,
      hasVersions ? strategyVersion : null,
    ],
    queryFn: () =>
      api.getAutoPaperEvidence({
        strategyVersion: hasVersions ? strategyVersion : undefined,
      }),
    enabled: (input?.enabled ?? true) && Boolean(effectiveAccountId),
    staleTime: 10_000,
    refetchInterval: 30_000,
    retry: false,
  });

  const verdict: PaperConfirmationVerdictV1 | null = useMemo(
    () => (query.data ? buildPaperEvidenceVerdictFromDto(query.data) : null),
    [query.data],
  );

  return {
    ...query,
    verdict,
    dto: query.data ?? null,
    accountId: effectiveAccountId,
  };
}
