import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type EstudioAutoTelemetry = Awaited<
  ReturnType<typeof api.getEstudioAutoTelemetry>
>["data"];

export function useEstudioAutoTelemetry(
  accountId: string | null | undefined,
  lookbackDays = 120,
) {
  return useQuery({
    queryKey: ["estudio-auto-telemetry", accountId, lookbackDays],
    queryFn: () =>
      api.getEstudioAutoTelemetry({
        accountId: accountId ?? undefined,
        lookbackDays,
      }),
    enabled: Boolean(accountId),
    staleTime: 60_000,
  });
}
