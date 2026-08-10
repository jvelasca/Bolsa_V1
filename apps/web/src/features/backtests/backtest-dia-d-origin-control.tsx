/**
 * Control de origen temporal junto al título Backtesting:
 * Hoy ↔ DÍA D + fecha concreta + carrusel (predeterminados / personalizados) + menú (…).
 */

import { ChevronDown, ChevronLeft, ChevronRight, Star } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { IconButton } from "@/components/ui/icon-button";
import { DiaDCarouselMenu } from "@/features/backtests/dia-d-carousel-menu";
import {
  addCustomDiaD,
  formatDiaDDisplay,
  loadDiaDCarouselPrefs,
  resolveDiaDCarouselChips,
  saveDiaDCarouselPrefs,
  startOfLocalYearIso,
  type DiaDCarouselPrefs,
} from "@/features/backtests/dia-d-favorites";
import {
  effectiveDiaD,
  isDiaDInPast,
  todayIsoDate,
} from "@/features/backtests/backtest-period";
import { cn } from "@/lib/utils";

type Props = {
  diaD: string;
  onDiaDChange: (next: string) => void;
  className?: string;
};

export function BacktestDiaDOriginControl({
  diaD,
  onDiaDChange,
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const [prefs, setPrefs] = useState<DiaDCarouselPrefs>(() =>
    loadDiaDCarouselPrefs(),
  );
  const [customLabel, setCustomLabel] = useState("");
  const rootRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const panelId = useId();
  const today = todayIsoDate();
  const active = effectiveDiaD(diaD);
  const past = isDiaDInPast(diaD);
  const chips = resolveDiaDCarouselChips(prefs);
  const activeInCustoms = prefs.customs.some((c) => c.iso === active);

  useEffect(() => {
    if (!open) return;
    const onDoc = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function persistPrefs(next: DiaDCarouselPrefs) {
    setPrefs(next);
    saveDiaDCarouselPrefs(next);
  }

  function selectToday() {
    onDiaDChange("");
  }

  function selectDiaD(iso: string) {
    const next = iso === today ? "" : iso;
    onDiaDChange(next);
  }

  function addActiveToCarousel() {
    if (!past) return;
    persistPrefs(addCustomDiaD(prefs, active, customLabel || undefined));
    setCustomLabel("");
  }

  function scrollBy(delta: number) {
    scrollRef.current?.scrollBy({ left: delta, behavior: "smooth" });
  }

  return (
    <div ref={rootRef} className={cn("relative", className)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        title={
          past
            ? `Origen DÍA D ${formatDiaDDisplay(active)} — embudo solo con datos ≤ esta fecha`
            : `Origen hoy ${formatDiaDDisplay(today)} — operativa en tiempo real del calendario`
        }
        onClick={() => setOpen((v) => !v)}
        className={cn(
          "inline-flex max-w-full items-center gap-1.5 rounded-md border px-2.5 py-1 text-left text-xs font-medium transition-colors",
          past
            ? "border-red-600 bg-red-600 text-white shadow-sm ring-2 ring-red-500/50 dark:border-red-500 dark:bg-red-600 dark:ring-red-400/40"
            : "border-border bg-muted/40 text-foreground hover:bg-muted/70",
        )}
      >
        <span className="min-w-0 truncate tabular-nums">
          {past ? (
            <>
              <span className="font-bold tracking-wide">DÍA D</span>
              <span className="opacity-90"> · </span>
              {formatDiaDDisplay(active)}
            </>
          ) : (
            <>
              <span className="font-semibold">Hoy</span>
              <span className="text-muted-foreground"> · </span>
              {formatDiaDDisplay(today)}
            </>
          )}
        </span>
        <ChevronDown
          className={cn("size-3.5 shrink-0 opacity-70", open && "rotate-180")}
          aria-hidden
        />
      </button>

      {open ? (
        <div
          id={panelId}
          role="dialog"
          aria-label="Origen temporal del backtesting"
          className="absolute left-0 top-[calc(100%+6px)] z-40 w-[min(100vw-2rem,28rem)] rounded-lg border border-border bg-background p-3 text-foreground shadow-lg ring-1 ring-black/10 dark:bg-zinc-950 dark:ring-white/10"
        >
          <p className="text-[11px] leading-snug text-muted-foreground">
            Carrusel como en Listas: predeterminados con (…) y fechas propias
            con Añadir ★ (editables/borrables en el menú).
          </p>

          <div className="mt-2.5 flex gap-1 rounded-md border border-border bg-muted p-0.5">
            <button
              type="button"
              className={cn(
                "flex-1 rounded px-2 py-1.5 text-[11px] font-medium",
                !past
                  ? "bg-background text-foreground shadow-sm"
                  : "bg-transparent text-muted-foreground hover:text-foreground",
              )}
              onClick={() => selectToday()}
            >
              Hoy · {formatDiaDDisplay(today)}
            </button>
            <button
              type="button"
              className={cn(
                "flex-1 rounded px-2 py-1.5 text-[11px] font-medium",
                past
                  ? "bg-amber-100 text-amber-950 shadow-sm dark:bg-amber-900 dark:text-amber-50"
                  : "bg-transparent text-muted-foreground hover:text-foreground",
              )}
              onClick={() => {
                if (!past) selectDiaD(startOfLocalYearIso());
              }}
            >
              DÍA D
            </button>
          </div>

          {/* Carrusel + (…) */}
          <div className="mt-3 flex min-w-0 items-center gap-0.5">
            <IconButton
              icon={ChevronLeft}
              title="Desplazar"
              className="shrink-0 opacity-70"
              onClick={() => scrollBy(-140)}
            />
            <div
              ref={scrollRef}
              className="scroll-area flex min-w-0 flex-1 items-center gap-1 overflow-x-auto py-0.5"
              role="tablist"
              aria-label="Carrusel DÍA D"
            >
              {chips.length === 0 ? (
                <span className="px-1 text-[10px] text-muted-foreground">
                  Activa predeterminados en (…) o añade una fecha ★
                </span>
              ) : (
                chips.map((chip) => {
                  const isActive = past && chip.iso === active;
                  return (
                    <button
                      key={chip.id}
                      type="button"
                      role="tab"
                      aria-selected={isActive}
                      title={`${chip.label} → ${formatDiaDDisplay(chip.iso)}`}
                      onClick={() => selectDiaD(chip.iso)}
                      className={cn(
                        "shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-medium transition-colors",
                        isActive
                          ? "border-amber-600 bg-amber-100 text-amber-950 dark:border-amber-500 dark:bg-amber-900 dark:text-amber-50"
                          : "border-border bg-muted/40 text-muted-foreground hover:border-primary/40 hover:text-foreground dark:bg-zinc-900",
                        chip.kind === "custom" &&
                          !isActive &&
                          "border-amber-500/35",
                      )}
                    >
                      <span className="max-w-[9rem] truncate">
                        {chip.label}
                      </span>
                    </button>
                  );
                })
              )}
            </div>
            <IconButton
              icon={ChevronRight}
              title="Desplazar"
              className="shrink-0 opacity-70"
              onClick={() => scrollBy(140)}
            />
            <DiaDCarouselMenu prefs={prefs} onPrefsChange={persistPrefs} />
          </div>

          <div className="mt-3 space-y-2 border-t border-border/70 pt-2.5">
            <p className="text-[10px] font-medium text-muted-foreground">
              Fecha determinada → personalizado
            </p>
            <div className="flex flex-wrap items-end gap-2">
              <label className="min-w-[9rem] flex-1 text-[10px] text-muted-foreground">
                Fecha
                <input
                  type="date"
                  max={today}
                  value={active}
                  onChange={(e) => selectDiaD(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground dark:bg-zinc-900"
                />
              </label>
              <label className="min-w-[7rem] flex-1 text-[10px] text-muted-foreground">
                Nombre (opc.)
                <input
                  type="text"
                  value={customLabel}
                  placeholder="p. ej. Crisis 2020"
                  onChange={(e) => setCustomLabel(e.target.value)}
                  className="mt-1 w-full rounded-md border border-border bg-background px-2 py-1.5 text-xs text-foreground dark:bg-zinc-900"
                />
              </label>
              <Button
                type="button"
                size="sm"
                variant={activeInCustoms ? "outline" : "default"}
                className="h-8 gap-1 px-2.5 text-[10px]"
                disabled={!past}
                title={
                  past
                    ? activeInCustoms
                      ? "Ya está en personalizados (edítalo en …)"
                      : "Añadir al carrusel como personalizado"
                    : "Elige una fecha pasada"
                }
                onClick={addActiveToCarousel}
              >
                <Star
                  className={cn(
                    "size-3.5",
                    activeInCustoms
                      ? "fill-amber-400 text-amber-400"
                      : undefined,
                  )}
                />
                {activeInCustoms ? "En carrusel" : "Añadir ★"}
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
