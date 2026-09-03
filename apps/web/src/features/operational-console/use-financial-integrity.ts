import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type FinancialIntegrity = Awaited<
  ReturnType<typeof api.getFinancialIntegrity>
>["data"];

export function useFinancialIntegrity(accountId: string | null | undefined) {
  return useQuery({
    queryKey: ["financial-integrity", accountId],
    queryFn: async () => {
      const res = await api.getFinancialIntegrity(accountId!);
      return res.data;
    },
    enabled: Boolean(accountId),
    staleTime: 15_000,
    refetchInterval: 30_000,
  });
}
