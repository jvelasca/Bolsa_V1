/**
 * Resumen compacto FA + TA para el diálogo (i) / hub Instrumentos.
 * Si falta FA, dispara sync Yahoo e informa del progreso.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { useEnsureInstrumentFundamentals } from "@/features/instruments/use-ensure-instrument-fundamentals";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KeyValueList, KeyValueRow } from "@/components/ui/key-value-list";

type Props = {
  instrumentId: string;
  symbol?: string;
};

function fmt(n: number | null | undefined, digits = 2): string {
  if (n == null || !Number.isFinite(n)) return "—";
  return n.toFixed(digits);
}

function scoreTone(score100: number | null | undefined): string {
  if (score100 == null) return "text-muted-foreground";
  if (score100 >= 70) return "text-emerald-600 dark:text-emerald-400";
  if (score100 >= 45) return "text-amber-600 dark:text-amber-400";
  return "text-destructive";
}

export function InstrumentAnalysisSummary({ instrumentId, symbol }: Props) {
  const { card, status, statusLabel, isRefreshing, refreshNow } =
    useEnsureInstrumentFundamentals(instrumentId);

  const compositeQuery = useQuery({
    queryKey: ["instrument-composite", instrumentId, "swing", "neutral"],
    queryFn: () =>
      api.getInstrumentComposite(instrumentId, {
        horizon: "swing",
        regime: "neutral",
      }),
    enabled: Boolean(instrumentId) && status === "ready",
    staleTime: 60_000,
  });

  const topQuery = useQuery({
    queryKey: ["instrument-strategy-top", instrumentId, "1d"],
    queryFn: () => api.getInstrumentStrategyTop(instrumentId, "1d"),
    enabled: Boolean(instrumentId),
    staleTime: 60_000,
  });

  const composite = compositeQuery.data?.data ?? null;
  const techLeg = composite?.legs?.find((l) => l.key === "technical");
  const fundLeg = composite?.legs?.find((l) => l.key === "fundamental");
  const topSlots =
    topQuery.data?.data?.slots?.filter((s) =>
      Boolean(s?.strategyDefinitionId),
    ) ?? [];

  const faBusy = status === "loading" || status === "refreshing";
  const showFaStatus = faBusy || status === "empty" || status === "error";

  return (
    <div className="max-h-[50vh] space-y-2 overflow-y-auto pr-1 text-xs">
      <div className="rounded-md border border-border/70 bg-muted/20 p-2.5">
        {/* auto-fit: lado a lado si caben ≥11.5rem; si no, apila */}
        <div className="grid gap-x-4 gap-y-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,11.5rem),1fr))]">
          <section className="min-w-0 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Fundamental
            </p>

            {showFaStatus ? (
              <div
                className={cn(
                  "rounded border px-2 py-1.5 text-[11px] leading-snug",
                  status === "error"
                    ? "border-destructive/40 bg-destructive/5 text-destructive"
                    : "border-border/60 bg-background/50 text-muted-foreground",
                )}
              >
                <p>{statusLabel}</p>
                {(status === "empty" || status === "error") && (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-2 h-7 text-[10px]"
                    disabled={isRefreshing}
                    onClick={() => refreshNow()}
                  >
                    Reintentar Yahoo
                  </Button>
                )}
              </div>
            ) : null}

            {status === "ready" && card ? (
              <>
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                  <span
                    className={cn(
                      "text-base font-semibold tabular-nums",
                      scoreTone(card.scoreDisplay100),
                    )}
                  >
                    {card.scoreDisplay100 != null
                      ? `${card.scoreDisplay100}/100`
                      : "—"}
                  </span>
                  <span className="text-[10px] text-muted-foreground">
                    {card.metadata?.confidence ?? "—"} · conf.
                  </span>
                </div>
                <KeyValueList>
                  <KeyValueRow label="PER">
                    {fmt(card.facts?.trailingPe, 1)}
                  </KeyValueRow>
                  <KeyValueRow label="ROE">
                    {fmt(
                      card.facts?.roe != null ? card.facts.roe * 100 : null,
                      1,
                    )}
                    %
                  </KeyValueRow>
                  <KeyValueRow label="Piotroski">
                    {card.derived?.piotroski ?? "—"}
                  </KeyValueRow>
                  <KeyValueRow label="ROIC">
                    {card.derived?.roic != null
                      ? `${(card.derived.roic * 100).toFixed(1)}%`
                      : "—"}
                  </KeyValueRow>
                  <KeyValueRow label="Beneish M">
                    {fmt(card.derived?.beneishM)}
                  </KeyValueRow>
                  <KeyValueRow label="WACC">
                    {card.derived?.wacc != null
                      ? `${(card.derived.wacc * 100).toFixed(1)}% (${card.derived.waccMethod ?? "—"})`
                      : "—"}
                  </KeyValueRow>
                </KeyValueList>
                {fundLeg ? (
                  <p className="text-[10px] text-muted-foreground">
                    Pierna FA: {fmt(fundLeg.score)} · {fundLeg.method ?? "—"}
                  </p>
                ) : null}
              </>
            ) : null}
          </section>

          <section className="min-w-0 space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
              Técnico
            </p>
            {composite ? (
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span
                  className={cn(
                    "text-base font-semibold tabular-nums",
                    scoreTone(composite.scoreDisplay100),
                  )}
                >
                  Comp.{" "}
                  {composite.scoreDisplay100 != null
                    ? `${composite.scoreDisplay100}/100`
                    : "—"}
                </span>
                <span className="text-[10px] text-muted-foreground">
                  {composite.metadata?.paperDUnlocked
                    ? "Paper D ok"
                    : "Paper D bloqueado"}
                </span>
              </div>
            ) : null}
            <KeyValueList>
              <KeyValueRow label="Pierna TA">
                {techLeg
                  ? `${fmt(techLeg.score)} · ${techLeg.method ?? "—"}`
                  : "—"}
              </KeyValueRow>
              <KeyValueRow label="Finalistas 1d">
                {topSlots.length || "—"}
              </KeyValueRow>
            </KeyValueList>
            {topSlots.slice(0, 3).map((slot, i) => (
              <p
                key={slot.strategyDefinitionId ?? i}
                className="truncate text-[10px] text-muted-foreground"
              >
                #{i + 1}{" "}
                {slot.label ?? slot.strategyDefinitionId ?? "estrategia"}
              </p>
            ))}
            {!composite && !compositeQuery.isLoading && status === "ready" ? (
              <p className="text-muted-foreground">
                Composite no disponible aún.
              </p>
            ) : null}
            {faBusy ? (
              <p className="text-muted-foreground">
                Composite tras completar FA…
              </p>
            ) : null}
          </section>
        </div>
      </div>

      <p className="text-[10px] leading-relaxed text-muted-foreground">
        Detalle en Backtesting →{" "}
        <Link
          to={`/backtests?instrumentId=${encodeURIComponent(instrumentId)}&focus=detail`}
          className="text-primary hover:underline"
        >
          técnico
        </Link>
        {" / "}
        <Link
          to={`/backtests?instrumentId=${encodeURIComponent(instrumentId)}&focus=fundamental`}
          className="text-primary hover:underline"
        >
          fundamental
        </Link>
        {symbol ? ` (${symbol})` : ""}.
      </p>
    </div>
  );
}
