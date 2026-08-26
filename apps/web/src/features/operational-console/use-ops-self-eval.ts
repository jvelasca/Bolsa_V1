import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type OpsSelfEvalReport = Awaited<ReturnType<typeof api.getOpsSelfEval>>;

export function useOpsSelfEval(
  accountId: string | null | undefined,
  lookbackDays = 120,
) {
  return useQuery({
    queryKey: ["ops-self-eval", accountId, lookbackDays],
    queryFn: () => api.getOpsSelfEval(accountId!, lookbackDays),
    enabled: Boolean(accountId),
    staleTime: 60_000,
    refetchInterval: 60_000,
  });
}

export function portfolioReconStatusFromReport(
  report: OpsSelfEvalReport | undefined,
): string | null {
  const recon = report?.portfolioReconciliation as
    | { status?: string }
    | undefined;
  return recon?.status ?? null;
}
