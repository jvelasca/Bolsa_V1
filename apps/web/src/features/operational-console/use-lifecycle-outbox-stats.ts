import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type LifecycleOutboxStats = Awaited<
  ReturnType<typeof api.getLifecycleOutboxStats>
>["data"];

export function useLifecycleOutboxStats(accountId: string | null | undefined) {
  return useQuery({
    queryKey: ["lifecycle-outbox-stats", accountId],
    queryFn: async () => {
      const res = await api.getLifecycleOutboxStats(accountId!);
      return res.data;
    },
    enabled: Boolean(accountId),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}
