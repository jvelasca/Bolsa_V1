/**
 * DÍA-D AUTO — panel del sandbox: declarado vs ejecutado, paso a paso.
 *
 * Read-only. Pinta el artefacto que produce el CLI `v2_89_dia_d_auto_replay.py`: un paso por
 * cada eslabón de la cadena AUTO, con la magnitud DECLARADA por el replay, la EJECUTADA real
 * (hechos durables de D, si existen) y su veredicto. Un valor no medido se rotula
 * `NO MEDIDO`; nunca se dibuja un 0 de relleno.
 */

import { useEffect, useMemo, useState } from "react";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { DiaDAutoFeedbackPanel } from "@/features/auto-monitor/dia-d-auto-feedback-panel";
import {
  useAutoDiaDReplay,
  useAutoDiaDReplayDays,
} from "@/features/auto-monitor/use-auto-dia-d-replay";

type DiaDAutoReplayDto = components["schemas"]["DiaDAutoReplayDto"];
type DiaDAutoStepDto = components["schemas"]["DiaDAutoStepDto"];

const VERDICT_STYLE: Record<string, string> = {
  MATCH: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  DIVERGENT: "bg-destructive/15 text-destructive",
  NOT_MEASURED: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  PARTIAL: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Un valor no medido es `NO MEDIDO`; nunca un `0` de relleno. */
export function formatDiaDValue(value: unknown): string {
  if (value === null || value === undefined) return "NO MEDIDO";
  if (typeof value === "number") {
    return Number.isInteger(value) ? String(value) : value.toFixed(2);
  }
  return String(value);
}

function VerdictBadge({ verdict }: { verdict: string }) {
  return (
    <span
      data-testid="dia-d-auto-step-verdict"
      data-verdict={verdict}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        VERDICT_STYLE[verdict] ?? "bg-muted text-muted-foreground",
      )}
    >
      {verdict}
    </span>
  );
}

function StepRow({ row }: { row: DiaDAutoStepDto }) {
  return (
    <tr
      data-testid="dia-d-auto-step"
      data-step={row.step}
      data-verdict={row.verdict}
      className="border-t border-border/50"
    >
      <td className="py-1.5 pr-3 font-mono text-[11px] text-foreground/90">
        {row.step}
      </td>
      <td className="py-1.5 pr-3 tabular-nums text-[11px]">
        {formatDiaDValue(row.declared)}
      </td>
      <td className="py-1.5 pr-3 tabular-nums text-[11px]">
        {formatDiaDValue(row.executed)}
      </td>
      <td className="py-1.5 pr-3">
        <VerdictBadge verdict={row.verdict} />
      </td>
      <td className="py-1.5 text-[10px] uppercase tracking-wide text-muted-foreground">
        {row.measurement}
      </td>
    </tr>
  );
}

function NotAvailable({ detail }: { detail: DiaDAutoReplayDto }) {
  const reason = detail.notes?.[0] ?? "artifact_not_found";
  const messages: Record<string, string> = {
    artifact_not_found:
      "No hay artefacto para este día. Ejecuta el sandbox por CLI para generarlo.",
    no_account_scope: "Sin cuenta activa: no se puede resolver el artefacto.",
    invalid_day: "Fecha inválida.",
    account_scope_mismatch: "El artefacto pertenece a otra cuenta.",
  };
  return (
    <Card
      className="rounded-xl border border-dashed border-border bg-card"
      data-testid="dia-d-auto-not-available"
      data-reason={reason}
    >
      <CardContent className="py-6">
        <p className="text-xs text-muted-foreground">
          {messages[reason] ?? reason}
        </p>
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">
          uv run --no-sync python
          apps/api-python/scripts/v2_89_dia_d_auto_replay.py --at {detail.day}{" "}
          --json
        </p>
      </CardContent>
    </Card>
  );
}

export function DiaDAutoSandbox() {
  const daysQuery = useAutoDiaDReplayDays();
  const [day, setDay] = useState<string | null>(null);
  const days = useMemo(() => daysQuery.data?.days ?? [], [daysQuery.data]);

  useEffect(() => {
    if (!day && days.length > 0) {
      setDay(days[0] ?? null);
    }
  }, [day, days]);

  const detailQuery = useAutoDiaDReplay(day);
  const detail = detailQuery.data;

  return (
    <div className="space-y-4" data-testid="dia-d-auto-panel">
      <Card className="rounded-xl border border-border bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">
            DÍA-D AUTO · sandbox read-only
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Simula el motor AUTO en una fecha pasada y contrasta lo declarado
            con lo ejecutado real. No sustituye la ventana PAPER.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <label
              className="text-[11px] text-muted-foreground"
              htmlFor="dia-d-auto-day"
            >
              Fecha D
            </label>
            <input
              id="dia-d-auto-day"
              data-testid="dia-d-auto-day-input"
              type="date"
              max={todayIso()}
              value={day ?? ""}
              onChange={(event) => setDay(event.target.value || null)}
              className="h-8 rounded-md border border-border bg-background px-2 text-xs tabular-nums"
            />
            {days.length > 0 ? (
              <span className="text-[10px] text-muted-foreground">
                {days.length} día(s) con artefacto
              </span>
            ) : null}
          </div>

          {days.length > 0 ? (
            <div
              className="flex flex-wrap gap-1.5"
              data-testid="dia-d-auto-days"
            >
              {days.map((available) => (
                <Button
                  key={available}
                  type="button"
                  size="sm"
                  variant={available === day ? "default" : "outline"}
                  className="h-6 rounded px-2 text-[10px] tabular-nums"
                  onClick={() => setDay(available)}
                >
                  {available}
                </Button>
              ))}
            </div>
          ) : null}
        </CardContent>
      </Card>

      {daysQuery.isLoading ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="dia-d-auto-loading"
        >
          Cargando días…
        </p>
      ) : null}

      {daysQuery.isError ? (
        <p className="text-sm text-destructive" data-testid="dia-d-auto-error">
          No se pudieron cargar los días del sandbox.
        </p>
      ) : null}

      {day === null && !daysQuery.isLoading ? (
        <p
          className="text-xs text-muted-foreground"
          data-testid="dia-d-auto-empty"
        >
          Elige una fecha D para ver la comparación declarado vs ejecutado.
        </p>
      ) : null}

      {detailQuery.isFetching && !detail ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="dia-d-auto-loading"
        >
          Cargando artefacto…
        </p>
      ) : null}

      {detail && !detail.available ? <NotAvailable detail={detail} /> : null}

      {detail && detail.available ? (
        <>
          <Card className="rounded-xl border border-border bg-card">
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-sm">{detail.day}</CardTitle>
                {detail.summary ? (
                  <div className="flex items-center gap-2">
                    <VerdictBadge verdict={detail.summary.verdict} />
                    <span
                      className="text-[10px] tabular-nums text-muted-foreground"
                      data-testid="dia-d-auto-summary"
                    >
                      match {detail.summary.match} · divergen{" "}
                      {detail.summary.divergent} · n/d{" "}
                      {detail.summary.notMeasured}
                    </span>
                  </div>
                ) : null}
              </div>
              <p className="text-[10px] text-muted-foreground">
                cuenta {String(detail.meta?.account ?? "—")} · versión{" "}
                {String(detail.meta?.versionA ?? "—")} · replay{" "}
                {String(detail.meta?.replayStart ?? "—")} →{" "}
                {String(detail.meta?.replayEnd ?? "—")}
              </p>
            </CardHeader>
            <CardContent>
              <table className="w-full" data-testid="dia-d-auto-steps">
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                    <th className="pb-1 pr-3 font-semibold">Paso</th>
                    <th className="pb-1 pr-3 font-semibold">Declarado</th>
                    <th className="pb-1 pr-3 font-semibold">Ejecutado</th>
                    <th className="pb-1 pr-3 font-semibold">Veredicto</th>
                    <th className="pb-1 font-semibold">Medición</th>
                  </tr>
                </thead>
                <tbody>
                  {(detail.steps ?? []).map((row) => (
                    <StepRow key={row.step} row={row} />
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          {detail.oos ? (
            <Card className="rounded-xl border border-border bg-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">
                  OOS real del ciclo de D
                </CardTitle>
              </CardHeader>
              <CardContent
                className="space-y-1 text-[11px]"
                data-testid="dia-d-auto-oos"
              >
                <p className="tabular-nums text-muted-foreground">
                  cerrados {detail.oos.closedCount} · vivos{" "}
                  {detail.oos.openCount} · R{" "}
                  {formatDiaDValue(detail.oos.realizedRTotal)} · n/d{" "}
                  {detail.oos.unmeasuredCount}
                </p>
                {(detail.oos.realized ?? []).length === 0 &&
                (detail.oos.open ?? []).length === 0 ? (
                  <p className="text-muted-foreground">
                    El ciclo abierto en D no se cerró dentro del horizonte
                    simulado.
                  </p>
                ) : null}
              </CardContent>
            </Card>
          ) : null}

          {detail.limits && detail.limits.length > 0 ? (
            <Card className="rounded-xl border border-amber-500/30 bg-amber-500/5">
              <CardContent className="py-3" data-testid="dia-d-auto-limits">
                <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
                  Límites declarados
                </p>
                <ul className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
                  {detail.limits.map((limit) => (
                    <li key={limit}>- {limit}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export type DiaDAutoView = "sandbox" | "feedback";

function DiaDAutoViewToolbar({
  view,
  onChange,
}: {
  view: DiaDAutoView;
  onChange: (view: DiaDAutoView) => void;
}) {
  return (
    <div
      role="tablist"
      aria-label="Vista del DÍA-D AUTO"
      data-testid="dia-d-auto-view-toolbar"
      className="inline-flex rounded-lg border border-border bg-muted/40 p-0.5"
    >
      {(
        [
          { id: "sandbox", label: "Sandbox por día" },
          { id: "feedback", label: "Feedback por valor" },
        ] as const
      ).map((option) => (
        <Button
          key={option.id}
          type="button"
          size="sm"
          variant="ghost"
          role="tab"
          aria-selected={view === option.id}
          data-testid={`dia-d-auto-view-${option.id}`}
          onClick={() => onChange(option.id)}
          className={cn(
            "h-7 rounded-md px-3 text-xs",
            view === option.id
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground",
          )}
        >
          {option.label}
        </Button>
      ))}
    </div>
  );
}

export function DiaDAutoPanel() {
  const [view, setView] = useState<DiaDAutoView>("sandbox");
  return (
    <div className="space-y-4" data-testid="dia-d-auto-root" data-view={view}>
      <DiaDAutoViewToolbar view={view} onChange={setView} />
      {view === "feedback" ? <DiaDAutoFeedbackPanel /> : <DiaDAutoSandbox />}
    </div>
  );
}
