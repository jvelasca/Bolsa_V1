/**
 * AUTO UI REFACTOR (F1) — semáforo de realidad monetaria visible en las 5 secciones.
 *
 * Montado en `AutoWorkspaceLayout` (sobre el `<Outlet />`) responde de un vistazo a la
 * primera duda del usuario básico: *¿esto es dinero real?* → **DINERO VIRTUAL · AUTO DEMO**.
 *
 * Cablea fuentes ya existentes (no re-deriva): cuenta activa, `account-summary` (misma
 * queryKey que el resto de la app), kill switch / `PAPER_D_EXECUTE`, prefs de libro y
 * armado local AUTO. El helper `buildAutoReality` decide el contenido; esta componente
 * sólo pinta.
 *
 * @see docs/engineering/spec-auto-cockpit-usuario-basico-2026-10-05.md §F1
 */

import { useQuery } from "@tanstack/react-query";
import { MeasurementValue } from "@/components/measurement-value";
import { formatPrice } from "@/features/charts/chart-utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import { loadAutoArm } from "@/features/trading/demo-book-auto-arm";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { AUTO_SIMULATION_BANNER } from "./auto-basic-home";
import {
  AUTO_REALITY_DISCLAIMER,
  buildAutoReality,
  type AutoRealityTone,
} from "./auto-reality";

/** Misma fuente/`staleTime` que `useMesaEntriesBlocked` (dedupe de React Query). */
const KILL_SWITCH_STALE_MS = 15_000;

/** Tono visual del semáforo: `unknown` (ámbar) nunca se funde con el verde de `virtual`. */
const TONE_CONTAINER_CLASS: Record<AutoRealityTone, string> = {
  virtual: "border-emerald-500/40 bg-emerald-500/10",
  real: "border-red-500/50 bg-red-500/10",
  unknown: "border-amber-500/50 bg-amber-500/10",
};

const TONE_DOT_CLASS: Record<AutoRealityTone, string> = {
  virtual: "bg-emerald-500",
  real: "bg-red-500",
  unknown: "bg-amber-500",
};

export function AutoRealityStrip() {
  const { account, effectiveAccountId } = useActiveAccount();
  const prefs = useDemoBookPrefs();
  const armed = loadAutoArm().armed;

  // La tira sólo consume `killOn`/`paperDExecuteEnv`, así que consulta el kill switch
  // directamente (misma `queryKey`) en vez de `useMesaEntriesBlocked`: así no dispara
  // las queries de decision-board/incidentes que no usa (coste por ruta en el shell).
  const killQuery = useQuery({
    queryKey: ["risk-kill-switch"],
    queryFn: () => api.getRiskKillSwitch(),
    staleTime: KILL_SWITCH_STALE_MS,
  });
  const killOn = killQuery.data?.effective === true;
  // Preserva la incertidumbre mientras la query no responde: `undefined` NO se colapsa a
  // `false` (eso convertiría «no medido» en una afirmación). Se declara `null` → NO MEDIDO.
  const paperDExecuteEnv = killQuery.data?.paperDExecuteEnv ?? null;

  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: async () =>
      (await api.getAccountSummary(effectiveAccountId!)).data,
    enabled: Boolean(effectiveAccountId),
  });

  const reality = buildAutoReality({
    accountType: account?.type ?? null,
    bookMode: prefs.mode,
    autoArmed: armed,
    paperDExecuteEnv,
  });

  const summary = summaryQuery.data;
  const capitalMeasurement = summary ? "COMPLETE" : "NO MEDIDO";

  return (
    <section
      aria-label="Realidad monetaria de AUTO"
      data-testid="auto-reality-strip"
      data-tone={reality.tone}
      className={cn(
        "mb-4 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border px-3 py-2 text-xs",
        TONE_CONTAINER_CLASS[reality.tone],
      )}
    >
      <span
        className="basis-full text-sm font-semibold"
        data-testid="auto-reality-banner"
      >
        {AUTO_SIMULATION_BANNER}
      </span>

      <span className="inline-flex items-center gap-1.5 font-semibold">
        <span
          aria-hidden="true"
          className={cn(
            "inline-block size-2 rounded-full",
            TONE_DOT_CLASS[reality.tone],
          )}
        />
        <span data-testid="auto-reality-money">{reality.moneyLabel}</span>
        <span aria-hidden="true">·</span>
        <span data-testid="auto-reality-mode">{reality.modeLabel}</span>
      </span>

      <span className="text-muted-foreground" data-testid="auto-reality-broker">
        {reality.brokerLabel}
      </span>

      <span className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-muted-foreground">
        <span data-testid="auto-reality-account">
          {reality.accountTypeLabel}
        </span>
        <span className="inline-flex items-center gap-1">
          Capital:
          <MeasurementValue
            value={summary?.totalEquity ?? null}
            measurement={capitalMeasurement}
            formatValue={(v) => formatPrice(Number(v))}
            testId="auto-reality-capital"
          />
        </span>
        <span data-testid="auto-reality-auto">
          AUTO: <strong className="font-semibold">{reality.autoLabel}</strong>
        </span>
      </span>

      {killOn ? (
        <span
          className="basis-full text-amber-600 dark:text-amber-400"
          data-testid="auto-reality-kill"
        >
          Entradas bloqueadas por el interruptor de seguridad (kill switch).
        </span>
      ) : null}

      <span className="basis-full text-[11px] text-muted-foreground">
        {AUTO_REALITY_DISCLAIMER}
      </span>

      {reality.notes.length > 0 ? (
        <span
          className="basis-full text-[11px] text-amber-600 dark:text-amber-400"
          data-testid="auto-reality-notes"
        >
          {reality.notes.join(" · ")}
        </span>
      ) : null}
    </section>
  );
}
