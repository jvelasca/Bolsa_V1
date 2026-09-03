import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type LifecycleReconciliation = Awaited<
  ReturnType<typeof api.getLifecycleReconciliation>
>["data"];

export function useLifecycleReconciliation(
  accountId: string | null | undefined,
) {
  return useQuery({
    queryKey: ["lifecycle-reconciliation", accountId],
    queryFn: async () => {
      const res = await api.getLifecycleReconciliation(accountId!);
      return res.data;
    },
    enabled: Boolean(accountId),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}
