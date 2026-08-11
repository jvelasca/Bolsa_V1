/**
 * Interruptor Supervisión ON — solo banner lista Estudio (ADR-024).
 *
 * Manual/SEMI/AUTO = barra de estado / Cuentas (no aquí).
 *
 * Banner: ON/OFF + chips de cadencia V·F·R (··· menú) + progreso (derecha).
 * Acciones Actualizar / Redescubrir → barra inferior de selección (no aquí).
 *
 * @see docs/engineering/estudio-supervision-model-2026-08-06.md
 * @see docs/engineering/estudio-process-status-ui-2026-08-06.md
 */

import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  FlaskConical,
  MoreHorizontal,
  Pause,
  Play,
  RefreshCcw,
} from "lucide-react";
import { OpaqueMenuPanel } from "@/components/ui/opaque-menu-panel";
import {
  ESTUDIO_FRESHNESS_PRESETS,
  ESTUDIO_REDISCOVER_PRESETS,
  ESTUDIO_SUPERVISION_EVENT,
  ESTUDIO_VIGILANCE_PRESETS,
  formatEstudioCadenceMinutes,
  loadEstudioSupervisionPrefs,
  patchEstudioSupervision,
  setEstudioSupervisionEnabled,
  type EstudioSupervisionPrefs,
} from "@/features/trading/estudio-supervision";
import {
  ESTUDIO_LANE_PURPOSE,
  type EstudioProcessLaneId,
} from "@/features/trading/estudio-process-status";
import {
  hasEstudioUpdatePauseCheckpoint,
  isEstudioUpdateSoftStopRequested,
  requestEstudioBannerSoftPause,
  requestListAutoSoftResume,
} from "@/features/trading/estudio-update-control";
import { resumeEstudioInstrumentsUpdate } from "@/features/trading/estudio-instruments-update";
import { ESTUDIO_LIST_ID } from "@bolsa/shared";
import { useListAutoActivityStore } from "@/stores/list-auto-activity-store";
import { cn } from "@/lib/utils";

export type EstudioBannerProgress = {
  current: number;
  total: number;
  label: string;
};

const LANE_ICON = {
  vigilance: Activity,
  freshness: FlaskConical,
  rediscover: RefreshCcw,
} as const;

const LANE_CHIP_TONE: Record<EstudioProcessLaneId, string> = {
  vigilance: "text-sky-600 dark:text-sky-400",
  freshness: "text-violet-600 dark:text-violet-400",
  rediscover: "text-amber-700 dark:text-amber-300",
};

const LANE_SHORT: Record<EstudioProcessLaneId, string> = {
  vigilance: "Vigilia",
  freshness: "Frescura",
  rediscover: "Redescubrir",
};

function useEstudioSupervisionPrefsState() {
  const [prefs, setPrefs] = useState<EstudioSupervisionPrefs>(() =>
    loadEstudioSupervisionPrefs(),
  );

  useEffect(() => {
    setPrefs(loadEstudioSupervisionPrefs());
    const onChange = () => setPrefs(loadEstudioSupervisionPrefs());
    window.addEventListener(ESTUDIO_SUPERVISION_EVENT, onChange);
    return () =>
      window.removeEventListener(ESTUDIO_SUPERVISION_EVENT, onChange);
  }, []);

  const onToggle = (enabled: boolean) => {
    setPrefs(setEstudioSupervisionEnabled(enabled));
  };

  const onPatch = (patch: Parameters<typeof patchEstudioSupervision>[0]) => {
    setPrefs(patchEstudioSupervision(patch));
  };

  return { prefs, onToggle, onPatch };
}

function CadenceField({
  lane,
  hint,
  value,
  presets,
  disabled,
  onChange,
  allowOff,
}: {
  lane: EstudioProcessLaneId;
  hint: string;
  value: number;
  presets: readonly number[];
  disabled?: boolean;
  onChange: (minutes: number) => void;
  allowOff?: boolean;
}) {
  const Icon = LANE_ICON[lane];
  const title = LANE_SHORT[lane];
  const options =
    allowOff || presets.includes(value) ? presets : [...presets, value];
  return (
    <div className="mb-2.5 space-y-1">
      <div className="flex items-center gap-1.5 text-[11px] font-semibold text-foreground">
        <Icon
          className={cn("h-3.5 w-3.5 shrink-0", LANE_CHIP_TONE[lane])}
          strokeWidth={2.4}
          aria-hidden
        />
        {title}
      </div>
      <p className="text-[11px] leading-snug text-foreground/80">{hint}</p>
      <select
        className="w-full rounded border border-border bg-background px-1.5 py-1 text-[11px] text-foreground"
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-label={title}
      >
        {options.map((m) => (
          <option key={m} value={m}>
            {m <= 0 ? "Desactivado" : `Cada ${formatEstudioCadenceMinutes(m)}`}
          </option>
        ))}
      </select>
    </div>
  );
}

function CadenceSummaryChips({
  prefs,
  onOpenMenu,
}: {
  prefs: EstudioSupervisionPrefs;
  onOpenMenu: () => void;
}) {
  const lanes: Array<{
    id: EstudioProcessLaneId;
    minutes: number;
  }> = [
    { id: "vigilance", minutes: prefs.vigilanceMinutes },
    { id: "freshness", minutes: prefs.freshnessMinutes },
    { id: "rediscover", minutes: prefs.rediscoverMinutes },
  ];

  return (
    <div
      className="inline-flex flex-wrap items-center gap-1"
      data-testid="estudio-cadence-chips"
      role="group"
      aria-label="Cadencias de supervisión Vigilia, Frescura y Redescubrir"
    >
      {lanes.map(({ id, minutes }) => {
        const Icon = LANE_ICON[id];
        const label = formatEstudioCadenceMinutes(minutes);
        const off = minutes <= 0;
        const title = [
          `${LANE_SHORT[id]}: cada ${label}`,
          ESTUDIO_LANE_PURPOSE[id],
          "Clic para configurar cadencias.",
        ].join("\n");
        return (
          <button
            key={id}
            type="button"
            onClick={onOpenMenu}
            title={title}
            aria-label={`${LANE_SHORT[id]}: ${label}`}
            className={cn(
              "inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5",
              "bg-background/80 font-medium tabular-nums transition-colors",
              "hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
              off
                ? "border-border/50 text-muted-foreground"
                : "border-border/80 text-foreground",
            )}
          >
            <Icon
              className={cn(
                "h-3 w-3 shrink-0",
                off ? "text-muted-foreground/60" : LANE_CHIP_TONE[id],
              )}
              strokeWidth={2.4}
              aria-hidden
            />
            <span className="text-[10px] leading-none tracking-tight">
              {off ? "off" : label}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function SupervisionCadenceMenu({
  prefs,
  onPatch,
  open,
  onOpenChange,
}: {
  prefs: EstudioSupervisionPrefs;
  onPatch: (patch: Parameters<typeof patchEstudioSupervision>[0]) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) onOpenChange(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onOpenChange(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, onOpenChange]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        className="rounded border border-border px-1.5 py-0.5 text-foreground hover:bg-accent"
        title="Configurar cadencias de supervisión"
        aria-label="Configurar cadencias de supervisión"
        aria-expanded={open}
        onClick={() => onOpenChange(!open)}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </button>
      {open ? (
        <OpaqueMenuPanel
          align="left"
          className="w-[300px] p-2.5 text-[11px] leading-snug"
        >
          <p className="mb-2 text-[12px] font-semibold text-foreground">
            Cadencias · vela diaria al cierre
          </p>
          <CadenceField
            lane="vigilance"
            hint="Revisa si el mandato / PnL paper se degrada. Con vela 1d basta 1× al día tras el cierre."
            value={prefs.vigilanceMinutes}
            presets={ESTUDIO_VIGILANCE_PRESETS}
            disabled={!prefs.enabled}
            onChange={(vigilanceMinutes) => onPatch({ vigilanceMinutes })}
          />
          <CadenceField
            lane="freshness"
            hint="Pase Lista AUTO: si Finalistas siguen válidos se omiten. Tras cada cierre nuevo."
            value={prefs.freshnessMinutes}
            presets={ESTUDIO_FRESHNESS_PRESETS}
            disabled={!prefs.enabled}
            onChange={(freshnessMinutes) => onPatch({ freshnessMinutes })}
          />
          <CadenceField
            lane="rediscover"
            hint="Embudo completo (caro). Solo N valores por pasada, en rotación."
            value={prefs.rediscoverMinutes}
            presets={ESTUDIO_REDISCOVER_PRESETS}
            disabled={!prefs.enabled}
            allowOff
            onChange={(rediscoverMinutes) => onPatch({ rediscoverMinutes })}
          />
          <div className="mb-1 space-y-1">
            <div className="text-[11px] font-semibold text-foreground">
              Presupuesto rediscubrimiento
            </div>
            <select
              className="w-full rounded border border-border bg-background px-1.5 py-1 text-[11px] text-foreground"
              value={prefs.rediscoverBudgetPerTick}
              disabled={!prefs.enabled || prefs.rediscoverMinutes <= 0}
              onChange={(e) =>
                onPatch({ rediscoverBudgetPerTick: Number(e.target.value) })
              }
              aria-label="Presupuesto rediscubrimiento"
            >
              {[3, 5, 10, 15, 20].map((n) => (
                <option key={n} value={n}>
                  {n} valores / pasada
                </option>
              ))}
            </select>
          </div>
          <p className="border-t border-border/60 pt-1.5 text-[10px] text-foreground/70">
            Los mismos iconos aparecen en cada fila (columna Procesos / bajo el
            nombre). Actualizar y Redescubrir están en la barra inferior al
            seleccionar valores.
          </p>
        </OpaqueMenuPanel>
      ) : null}
    </div>
  );
}

/** Banner compacto encima de la lista Estudio (watchlist). */
export function EstudioListSupervisionBanner({
  progress = null,
}: {
  /** Progreso local de «Actualizar» (prioridad sobre Lista AUTO). */
  progress?: EstudioBannerProgress | null;
}) {
  const { prefs, onToggle, onPatch } = useEstudioSupervisionPrefsState();
  const [menuOpen, setMenuOpen] = useState(false);
  const listAutoActive = useListAutoActivityStore((s) => s.active);
  const listAutoListId = useListAutoActivityStore((s) => s.listId);
  const listAutoIndex = useListAutoActivityStore((s) => s.index);
  const listAutoTotal = useListAutoActivityStore((s) => s.total);
  const listAutoSymbol = useListAutoActivityStore((s) => s.symbol);
  const listAutoDetail = useListAutoActivityStore((s) => s.detail);
  const listAutoPaused = useListAutoActivityStore((s) => s.paused);

  const softStopPending =
    isEstudioUpdateSoftStopRequested() ||
    Boolean(listAutoDetail?.startsWith("Termina "));
  const updatePaused =
    listAutoPaused &&
    (hasEstudioUpdatePauseCheckpoint() ||
      Boolean(listAutoDetail?.startsWith("Pausa ·")));
  const stoppingOrPaused = listAutoPaused || softStopPending;

  const activity = useMemo((): EstudioBannerProgress | null => {
    // Pausa / «Termina…» tienen prioridad sobre el progreso local (que el padre limpia).
    if (
      listAutoActive &&
      listAutoListId === ESTUDIO_LIST_ID &&
      listAutoTotal > 0 &&
      (softStopPending || updatePaused || listAutoPaused)
    ) {
      return {
        current: Math.min(listAutoIndex + 1, listAutoTotal),
        total: listAutoTotal,
        label:
          listAutoDetail?.slice(0, 52) ||
          (softStopPending
            ? `Termina ${listAutoSymbol || "…"} y para…`
            : `Pausa · ${listAutoSymbol || "…"}`),
      };
    }
    if (progress && progress.total > 0) {
      return progress;
    }
    if (
      listAutoActive &&
      listAutoListId === ESTUDIO_LIST_ID &&
      listAutoTotal > 0
    ) {
      return {
        current: Math.min(listAutoIndex + 1, listAutoTotal),
        total: listAutoTotal,
        label: listAutoDetail?.slice(0, 40) || listAutoSymbol || "Procesando…",
      };
    }
    return null;
  }, [
    progress,
    listAutoActive,
    listAutoListId,
    listAutoIndex,
    listAutoTotal,
    listAutoSymbol,
    listAutoDetail,
    listAutoPaused,
    softStopPending,
    updatePaused,
  ]);

  const pct =
    activity && activity.total > 0
      ? Math.min(100, Math.round((activity.current / activity.total) * 100))
      : 0;

  const canSoftPause = Boolean(activity) && !stoppingOrPaused;
  /** ▶ solo cuando ya paró (no mientras «Termina…»). */
  const canResume = Boolean(activity) && listAutoPaused && !softStopPending;

  return (
    <div
      className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/30 px-2 py-1.5 text-[11px]"
      data-testid="estudio-list-supervision-banner"
    >
      <label className="flex cursor-pointer items-center gap-1.5 font-semibold text-foreground">
        <input
          type="checkbox"
          className="rounded border-border"
          checked={prefs.enabled}
          onChange={(e) => onToggle(e.target.checked)}
        />
        Supervisión {prefs.enabled ? "ON" : "OFF"}
      </label>
      {prefs.enabled ? (
        <CadenceSummaryChips
          prefs={prefs}
          onOpenMenu={() => setMenuOpen(true)}
        />
      ) : null}
      <SupervisionCadenceMenu
        prefs={prefs}
        onPatch={onPatch}
        open={menuOpen}
        onOpenChange={setMenuOpen}
      />
      {activity ? (
        <div
          className="ml-auto flex min-w-[10rem] max-w-[18rem] items-center gap-1.5"
          data-testid="estudio-banner-progress"
        >
          <div
            className="flex min-w-0 flex-1 flex-col gap-0.5"
            title={`${activity.label} · ${activity.current}/${activity.total}`}
          >
            <div className="flex items-center justify-between gap-2 text-[10px] text-foreground/85">
              <span className="min-w-0 truncate font-medium">
                {activity.label}
              </span>
              <span className="shrink-0 tabular-nums text-muted-foreground">
                {activity.current}/{activity.total}
              </span>
            </div>
            <div className="h-1 overflow-hidden rounded-sm bg-border/80">
              <div
                className={cn(
                  "h-full rounded-sm transition-[width] duration-300",
                  stoppingOrPaused ? "bg-amber-500" : "bg-sky-500",
                )}
                style={{
                  width: `${Math.max(pct, activity.current > 0 ? 8 : 0)}%`,
                }}
              />
            </div>
          </div>
          {canSoftPause ? (
            <button
              type="button"
              className="shrink-0 rounded border border-border/70 bg-background/70 p-0.5 text-muted-foreground hover:bg-accent hover:text-foreground"
              title="Pausa: termina el valor en curso y no sigue"
              aria-label="Pausa suave: termina el valor en curso y para"
              data-testid="estudio-banner-soft-pause"
              onClick={() => requestEstudioBannerSoftPause()}
            >
              <Pause className="h-3 w-3" />
            </button>
          ) : null}
          {canResume ? (
            <button
              type="button"
              className="shrink-0 rounded border border-primary/40 bg-primary/10 p-0.5 text-primary hover:bg-primary/20"
              title="Reanudar: continúa desde donde se pausó"
              aria-label="Reanudar"
              data-testid="estudio-banner-soft-resume"
              onClick={() => {
                if (hasEstudioUpdatePauseCheckpoint()) {
                  void resumeEstudioInstrumentsUpdate();
                  return;
                }
                requestListAutoSoftResume();
              }}
            >
              <Play className="h-3 w-3 fill-current" />
            </button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function EstudioSupervisionPanel({
  compact = false,
}: {
  compact?: boolean;
}) {
  const { prefs, onToggle, onPatch } = useEstudioSupervisionPrefsState();
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div
      className={
        compact
          ? "space-y-1.5 rounded border border-border/60 bg-background/40 px-2 py-1.5"
          : "space-y-2 rounded border border-border p-2"
      }
      data-testid="estudio-supervision-panel"
    >
      <div className="flex items-center justify-between gap-2">
        <label className="flex cursor-pointer items-center gap-1.5 text-[12px] font-medium text-foreground">
          <input
            type="checkbox"
            className="rounded border-border"
            checked={prefs.enabled}
            onChange={(e) => onToggle(e.target.checked)}
          />
          Supervisión ON
        </label>
        <div className="flex items-center gap-1.5">
          {prefs.enabled ? (
            <CadenceSummaryChips
              prefs={prefs}
              onOpenMenu={() => setMenuOpen(true)}
            />
          ) : null}
          <SupervisionCadenceMenu
            prefs={prefs}
            onPatch={onPatch}
            open={menuOpen}
            onOpenChange={setMenuOpen}
          />
        </div>
      </div>
    </div>
  );
}
