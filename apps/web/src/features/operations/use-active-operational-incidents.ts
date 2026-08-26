import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useActiveOperationalIncidents(
  accountId: string | null | undefined,
) {
  return useQuery({
    queryKey: ["operational-incidents-active", accountId],
    queryFn: () => api.getActiveOperationalIncidents(accountId!),
    enabled: Boolean(accountId),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}
