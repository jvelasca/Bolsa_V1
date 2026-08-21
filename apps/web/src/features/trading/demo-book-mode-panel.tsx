/**
 * Controles del libro operativo de la cuenta activa: MANUAL/SEMI.
 * R-12 C3 — AUTO de cuenta no disponible en BETA (no se presenta como modo usable).
 * Título UI = nombre de la cuenta activa (no «Libro DEMO»).
 *
 * No confundir con Lista AUTO del Laboratorio (`list-auto-activity-store`).
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import {
  DEMO_BOOK_AUTO_FOOTER,
  DEMO_BOOK_AUTO_TOOLTIP,
  DEMO_BOOK_AUTO_UI_ENABLED,
  DEMO_BOOK_AUTO_UNAVAILABLE_LABEL,
} from "@/features/trading/demo-book-auto-copy";
import {
  DEMO_BOOK_MAX_OPEN_MAX,
  DEMO_BOOK_MAX_OPEN_MIN,
  DEMO_BOOK_SIZE_PCT_MAX,
  DEMO_BOOK_SIZE_PCT_MIN,
  patchDemoBookPrefs,
  type DemoBookCountryPrefer,
  type DemoBookMode,
  type DemoBookPrefs,
} from "@/features/trading/demo-book-prefs";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";

const MODE_LABEL: Record<Exclude<DemoBookMode, "auto">, string> = {
  manual: "Manual",
  semi: "Semi",
};

const GEO_LABEL: Record<DemoBookCountryPrefer, string> = {
  home_first: "País primero",
  europe_first: "Europa primero",
  global_ok: "Sin preferencia",
};

type Props = {
  className?: string;
  compact?: boolean;
};

export function DemoBookModePanel({ className, compact }: Props) {
  const { account } = useActiveAccount();
  const prefs = useDemoBookPrefs();
  const accountTitle = account?.name?.trim() || "Sin cuenta activa";
  const qc = useQueryClient();

  const killQ = useQuery({
    queryKey: ["risk-kill-switch"],
    queryFn: () => api.getRiskKillSwitch(),
    refetchInterval: 15_000,
  });

  const killMut = useMutation({
    mutationFn: (enabled: boolean) => api.setRiskKillSwitch(enabled),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["risk-kill-switch"] });
    },
  });

  function update(patch: Partial<DemoBookPrefs>) {
    patchDemoBookPrefs(patch);
  }

  const killOn = Boolean(killQ.data?.effective);

  return (
    <div
      className={cn(
        "space-y-2 rounded-md border border-border/80 bg-muted/20 p-2 text-[11px]",
        className,
      )}
      data-testid="demo-book-mode-panel"
    >
      <p className="font-medium text-foreground" title={accountTitle}>
        <span className="line-clamp-2">{accountTitle}</span>
        {!compact ? (
          <span className="ml-1 font-normal text-muted-foreground">
            · operativa
          </span>
        ) : null}
      </p>
      <div className="flex flex-wrap gap-1">
        {(["manual", "semi"] as const).map((mode) => {
          const active = prefs.mode === mode;
          return (
            <button
              key={mode}
              type="button"
              title={
                mode === "manual"
                  ? "Solo avisos · sin Confirm automático"
                  : "Propuestas → Confirm F3 → DEMO"
              }
              onClick={() => update({ mode })}
              className={cn(
                "rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors",
                active
                  ? "border-emerald-500 bg-emerald-500/15 text-emerald-800 dark:text-emerald-300"
                  : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground",
              )}
            >
              {MODE_LABEL[mode]}
            </button>
          );
        })}
        {DEMO_BOOK_AUTO_UI_ENABLED ? (
          <button
            type="button"
            title={DEMO_BOOK_AUTO_TOOLTIP}
            onClick={() => update({ mode: "auto" })}
            className={cn(
              "rounded-full border px-2 py-0.5 text-[10px] font-medium transition-colors",
              prefs.mode === "auto"
                ? "border-emerald-500 bg-emerald-500/15 text-emerald-800 dark:text-emerald-300"
                : "border-border text-muted-foreground hover:border-primary/40 hover:text-foreground",
            )}
          >
            Auto
          </button>
        ) : (
          <span
            className="cursor-default rounded-full border border-dashed border-border px-2 py-0.5 text-[10px] font-medium text-muted-foreground/70"
            data-testid="demo-book-auto-unavailable"
            title={DEMO_BOOK_AUTO_TOOLTIP}
          >
            AUTO · {DEMO_BOOK_AUTO_UNAVAILABLE_LABEL}
          </span>
        )}
      </div>

      <div
        className="flex flex-wrap items-center gap-1.5 border-t border-border/60 pt-1.5"
        data-testid="demo-book-kill-switch"
      >
        <button
          type="button"
          className={cn(
            "rounded border px-2 py-0.5 text-[10px] font-medium",
            killOn
              ? "border-red-500/60 bg-red-500/15 text-red-800 dark:text-red-300"
              : "border-border text-muted-foreground hover:text-foreground",
          )}
          disabled={killMut.isPending}
          title="OR-P7: bloquea aperturas automáticas (Risk Engine) en &lt;1s"
          onClick={() => killMut.mutate(!killOn)}
        >
          {killOn ? "Kill switch ON" : "Kill switch off"}
        </button>
      </div>

      <div
        className={cn("grid gap-1.5", compact ? "grid-cols-1" : "grid-cols-2")}
      >
        <label className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">Máx. posiciones</span>
          <input
            type="number"
            min={DEMO_BOOK_MAX_OPEN_MIN}
            max={DEMO_BOOK_MAX_OPEN_MAX}
            value={prefs.maxOpenPositions}
            onChange={(e) =>
              update({ maxOpenPositions: Number(e.target.value) })
            }
            className="rounded border border-border bg-background px-1.5 py-1 text-foreground"
          />
        </label>
        <label className="flex flex-col gap-0.5">
          <span className="text-muted-foreground">% cash / op</span>
          <input
            type="number"
            min={DEMO_BOOK_SIZE_PCT_MIN}
            max={DEMO_BOOK_SIZE_PCT_MAX}
            value={prefs.defaultSizePctOfCash}
            onChange={(e) =>
              update({ defaultSizePctOfCash: Number(e.target.value) })
            }
            className="rounded border border-border bg-background px-1.5 py-1 text-foreground"
            title="Por defecto ~10% del efectivo disponible"
          />
        </label>
        <label
          className={cn("flex flex-col gap-0.5", compact ? "" : "col-span-2")}
        >
          <span className="text-muted-foreground">Preferencia geo</span>
          <select
            value={prefs.countryPrefer}
            onChange={(e) =>
              update({ countryPrefer: e.target.value as DemoBookCountryPrefer })
            }
            className="rounded border border-border bg-background px-1.5 py-1 text-foreground"
            title="Suave: no bloquea óptimos de otras zonas"
          >
            {(Object.keys(GEO_LABEL) as DemoBookCountryPrefer[]).map((k) => (
              <option key={k} value={k}>
                {GEO_LABEL[k]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <p className="text-[10px] leading-snug text-muted-foreground">
        {DEMO_BOOK_AUTO_FOOTER}
      </p>
    </div>
  );
}
