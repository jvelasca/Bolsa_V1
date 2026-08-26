import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";

/** OR-6 — venue efectivo (PA-1 coalesce), no solo el toggle global de mesa. */
export function useEffectiveBrokerVenue(): "paper" | "live" {
  const { effectiveAccountId } = useActiveAccount();
  const venueQuery = useQuery({
    queryKey: ["broker-venue"],
    queryFn: () => api.getBrokerVenue(),
    staleTime: 15_000,
  });
  const accountVenueQuery = useQuery({
    queryKey: ["account-broker-venue", effectiveAccountId],
    queryFn: () => api.getAccountBrokerVenue(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 15_000,
  });
  return (
    accountVenueQuery.data?.effective ?? venueQuery.data?.brokerVenue ?? "paper"
  );
}
