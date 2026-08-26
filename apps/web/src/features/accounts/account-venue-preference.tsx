/**
 * OR-6 / PA-1 — preferencia Paper|Live por cuenta (settings_json.brokerVenue).
 * ≠ toggle global de mesa (VS-1/RV-1 gana en coalesce).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type BrokerVenue = "paper" | "live";

export function AccountVenuePreference({ accountId }: { accountId: string }) {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["account-broker-venue", accountId],
    queryFn: () => api.getAccountBrokerVenue(accountId),
    staleTime: 15_000,
  });
  const mut = useMutation({
    mutationFn: (venue: BrokerVenue) =>
      api.setAccountBrokerVenue(accountId, venue),
    onSuccess: () => {
      void qc.invalidateQueries({
        queryKey: ["account-broker-venue", accountId],
      });
      void qc.invalidateQueries({ queryKey: ["ops-self-eval"] });
      void qc.invalidateQueries({ queryKey: ["accounts"] });
    },
  });

  const preference = query.data?.preference ?? null;
  const effective = query.data?.effective ?? "paper";

  return (
    <div
      className="space-y-2 rounded-lg border border-border p-3"
      data-testid="account-venue-preference"
    >
      <p className="text-sm font-medium">Venue de ejecución (cuenta)</p>
      <p className="text-xs text-muted-foreground">
        Preferencia Paper | Live de esta cuenta. El toggle de mesa es un
        override global (gana sobre esta preferencia). LIVE es experimental:
        submitted ≠ fill · trading not accepted.
      </p>
      <div className="flex flex-wrap items-center gap-1.5">
        {(["paper", "live"] as const).map((v) => {
          const active = (preference ?? effective) === v;
          return (
            <button
              key={v}
              type="button"
              disabled={mut.isPending || query.isLoading}
              className={cn(
                "rounded border px-2 py-1 text-xs font-medium capitalize",
                active
                  ? "border-primary/50 bg-primary/10 text-foreground"
                  : "border-border text-muted-foreground opacity-70",
              )}
              data-testid={`account-venue-preference-${v}`}
              onClick={() => {
                if (!active) mut.mutate(v);
              }}
            >
              {v === "paper" ? "Paper" : "Live"}
            </button>
          );
        })}
        <span className="text-[11px] text-muted-foreground">
          Efectivo ahora: {effective === "live" ? "LIVE" : "PAPER"}
          {preference == null ? " · sin preferencia (cae al global/env)" : ""}
        </span>
      </div>
      {mut.isError ? (
        <p className="text-xs text-destructive">
          No se pudo guardar la preferencia de venue.
        </p>
      ) : null}
    </div>
  );
}
