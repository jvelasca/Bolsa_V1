/**
 * DÍA-D AUTO · FEEDBACK — vista descriptiva + gráfica por valor.
 *
 * Read-only. Consume el artefacto que produce `v2_90_dia_d_feedback.py`: veredicto por
 * instrumento (OOS_SUPPORTED/MIXED/REFUTED/NOT_MEASURED), resumen global, tabla por valor,
 * heatmap valor × día, curva de R acumulado y catálogo de errores. Un valor no medido se
 * rotula `NO MEDIDO`; nunca se dibuja un 0 de relleno.
 */

import { useEffect, useMemo, useState } from "react";
import type { components } from "@/api/schema";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  useAutoDiaDFeedback,
  useAutoDiaDFeedbackList,
} from "@/features/auto-monitor/use-auto-dia-d-feedback";
import { DiaDAutoFeedbackHeatmap } from "@/features/auto-monitor/dia-d-auto-feedback-heatmap";
import { DiaDAutoFeedbackChart } from "@/features/auto-monitor/dia-d-auto-feedback-chart";
import { DiaDAutoErrorList } from "@/features/auto-monitor/dia-d-auto-error-list";

type DiaDFeedbackDto = components["schemas"]["DiaDFeedbackDto"];
type DiaDFeedbackValueDto = components["schemas"]["DiaDFeedbackValueDto"];

const VERDICT_STYLE: Record<string, string> = {
  OOS_SUPPORTED: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  MIXED: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  REFUTED: "bg-destructive/15 text-destructive",
  NOT_MEASURED: "bg-muted text-muted-foreground",
};

// `OOS_SUPPORTED` NO es "confirmado": es evidencia del REPLAY/OOS, no de la ejecución PAPER.
// `CONFIRMED` queda reservado para evidencia PAPER y no se emite todavía.
const VERDICT_LABEL: Record<string, string> = {
  OOS_SUPPORTED: "Soportado OOS",
  MIXED: "Mixto",
  REFUTED: "Refutado",
  NOT_MEASURED: "NO MEDIDO",
};

const EVIDENCE_STYLE: Record<string, string> = {
  STRONG: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
  SUPPORTED: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
  PRELIMINARY: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
  NOT_MEASURED: "bg-muted text-muted-foreground",
};

const EVIDENCE_LABEL: Record<string, string> = {
  STRONG: "Fuerte",
  SUPPORTED: "Soportada",
  PRELIMINARY: "Preliminar",
  NOT_MEASURED: "NO MEDIDO",
};

/** Un valor no medido se rotula `NO MEDIDO`; nunca un `0` de relleno. */
export function formatFeedbackR(value: number | null | undefined): string {
  if (value === null || value === undefined) return "NO MEDIDO";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
}

export function formatFeedbackHit(value: number | null | undefined): string {
  if (value === null || value === undefined) return "NO MEDIDO";
  return `${Math.round(value * 100)}%`;
}

function VerdictBadge({ verdict }: { verdict: string }) {
  return (
    <span
      data-testid="dia-d-auto-feedback-verdict"
      data-verdict={verdict}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        VERDICT_STYLE[verdict] ?? "bg-muted text-muted-foreground",
      )}
    >
      {VERDICT_LABEL[verdict] ?? verdict}
    </span>
  );
}

function EvidenceBadge({ quality }: { quality: string }) {
  return (
    <span
      data-testid="dia-d-auto-feedback-evidence"
      data-evidence={quality}
      className={cn(
        "rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
        EVIDENCE_STYLE[quality] ?? "bg-muted text-muted-foreground",
      )}
      title="Calidad de la muestra (NOT_MEASURED <5 · PRELIMINARY 5-19 · SUPPORTED 20-31 · STRONG >=32)"
    >
      {EVIDENCE_LABEL[quality] ?? quality}
    </span>
  );
}

function ValueRow({ value }: { value: DiaDFeedbackValueDto }) {
  return (
    <tr
      data-testid="dia-d-auto-feedback-value"
      data-symbol={value.symbol}
      data-verdict={value.verdict}
      className="border-t border-border/50"
    >
      <td className="py-1.5 pr-3 font-mono text-[11px] text-foreground/90">
        {value.symbol}
      </td>
      <td className="py-1.5 pr-3">
        <VerdictBadge verdict={value.verdict} />
      </td>
      <td className="py-1.5 pr-3">
        <EvidenceBadge quality={value.evidenceQuality} />
      </td>
      <td
        className="py-1.5 pr-3 tabular-nums text-[11px]"
        title={value.verdictReason ?? undefined}
      >
        {formatFeedbackR(value.expectancyR)}
      </td>
      <td className="py-1.5 pr-3 tabular-nums text-[11px]">
        {formatFeedbackHit(value.hitRate)}
      </td>
      <td className="py-1.5 pr-3 tabular-nums text-[11px]">
        {value.measuredCycles}
        <span className="text-muted-foreground">
          /{value.limits?.minCycles ?? "—"}
        </span>
      </td>
      <td className="py-1.5 pr-3 tabular-nums text-[11px]">
        {value.daysCovered}/{value.windowDays}
      </td>
      <td
        className="py-1.5 tabular-nums text-[11px]"
        data-errors={value.errorTotal}
      >
        {value.errorTotal}
      </td>
    </tr>
  );
}

function NotAvailable({ detail }: { detail: DiaDFeedbackDto }) {
  const reason = detail.notes?.[0] ?? "artifact_not_found";
  const messages: Record<string, string> = {
    artifact_not_found:
      "No hay artefacto de feedback para esta ventana. Ejecuta el barrido por CLI para generarlo.",
    no_account_scope: "Sin cuenta activa: no se puede resolver el artefacto.",
    invalid_window: "Ventana inválida.",
  };
  return (
    <Card
      className="rounded-xl border border-dashed border-border bg-card"
      data-testid="dia-d-auto-feedback-not-available"
      data-reason={reason}
    >
      <CardContent className="py-6">
        <p className="text-xs text-muted-foreground">
          {messages[reason] ?? reason}
        </p>
        <p className="mt-2 font-mono text-[10px] text-muted-foreground">
          uv run --no-sync python
          apps/api-python/scripts/v2_90_dia_d_feedback.py --from D0 --to D1
          --json
        </p>
      </CardContent>
    </Card>
  );
}

export function DiaDAutoFeedbackPanel() {
  const listQuery = useAutoDiaDFeedbackList();
  const windows = useMemo(
    () => listQuery.data?.windows ?? [],
    [listQuery.data],
  );
  const latest = listQuery.data?.latest ?? null;
  const [window, setWindow] = useState<string | null>(null);

  useEffect(() => {
    if (!window && latest) {
      setWindow(latest);
    }
  }, [window, latest]);

  const detailQuery = useAutoDiaDFeedback(window);
  const artifact =
    detailQuery.data ??
    (window !== null && window === latest
      ? (listQuery.data?.artifact ?? null)
      : null);

  const days = artifact?.window?.days ?? [];

  return (
    <div className="space-y-4" data-testid="dia-d-auto-feedback-panel">
      <Card className="rounded-xl border border-border bg-card">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm">
            DÍA-D AUTO · feedback por valor
          </CardTitle>
          <p className="text-[11px] text-muted-foreground">
            Confirma o refuta la operativa de cada instrumento sobre una ventana
            y cataloga los errores de software/operativa/dato. Advisory
            read-only: no cambia el motor.
          </p>
        </CardHeader>
        <CardContent className="space-y-3">
          {windows.length > 0 ? (
            <div
              className="flex flex-wrap gap-1.5"
              data-testid="dia-d-auto-feedback-windows"
            >
              {windows.map((available) => (
                <Button
                  key={available}
                  type="button"
                  size="sm"
                  variant={available === window ? "default" : "outline"}
                  className="h-6 rounded px-2 text-[10px] tabular-nums"
                  onClick={() => setWindow(available)}
                >
                  {available.replace("_", "→")}
                </Button>
              ))}
            </div>
          ) : null}

          {artifact?.gate ? (
            <p
              className="text-[10px] text-muted-foreground"
              data-testid="dia-d-auto-feedback-gate"
            >
              Gate de ventana{" "}
              <span className="font-semibold text-foreground/80">
                {String(artifact.gate.verdict ?? "—")}
              </span>{" "}
              · días {String(artifact.gate.days ?? "—")} · episodios{" "}
              {String(artifact.gate.episodes ?? "—")} · ciclos{" "}
              {String(artifact.gate.cycles ?? "—")}
            </p>
          ) : null}
        </CardContent>
      </Card>

      {listQuery.isLoading ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="dia-d-auto-feedback-loading"
        >
          Cargando ventanas…
        </p>
      ) : null}

      {listQuery.isError ? (
        <p
          className="text-sm text-destructive"
          data-testid="dia-d-auto-feedback-error"
        >
          No se pudieron cargar las ventanas de feedback.
        </p>
      ) : null}

      {window === null && !listQuery.isLoading && !listQuery.isError ? (
        <p
          className="text-xs text-muted-foreground"
          data-testid="dia-d-auto-feedback-empty"
        >
          Elige una ventana para ver el veredicto por valor.
        </p>
      ) : null}

      {artifact && !artifact.available ? (
        <NotAvailable detail={artifact} />
      ) : null}

      {artifact && artifact.available ? (
        <>
          <Card className="rounded-xl border border-border bg-card">
            <CardHeader className="pb-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <CardTitle className="text-sm">
                  {artifact.window?.from} → {artifact.window?.to}
                </CardTitle>
                {artifact.summary ? (
                  <span
                    className="text-[10px] tabular-nums text-muted-foreground"
                    data-testid="dia-d-auto-feedback-summary"
                  >
                    soportados OOS {artifact.summary.oosSupported} · mixtos{" "}
                    {artifact.summary.mixed} · refutados{" "}
                    {artifact.summary.refuted} · n/d{" "}
                    {artifact.summary.notMeasured}
                  </span>
                ) : null}
              </div>
              {artifact.summary ? (
                <p className="text-[10px] text-muted-foreground">
                  errores software {artifact.summary.errors?.SOFTWARE ?? 0} ·
                  operativa {artifact.summary.errors?.OPERATIONAL ?? 0} · datos{" "}
                  {artifact.summary.errors?.DATA ?? 0}
                </p>
              ) : null}
            </CardHeader>
            <CardContent>
              <table
                className="w-full"
                data-testid="dia-d-auto-feedback-values"
              >
                <thead>
                  <tr className="text-left text-[10px] uppercase tracking-wide text-muted-foreground">
                    <th className="pb-1 pr-3 font-semibold">Valor</th>
                    <th className="pb-1 pr-3 font-semibold">Veredicto</th>
                    <th className="pb-1 pr-3 font-semibold">Evidencia</th>
                    <th className="pb-1 pr-3 font-semibold">R medio</th>
                    <th className="pb-1 pr-3 font-semibold">Hit</th>
                    <th className="pb-1 pr-3 font-semibold">n</th>
                    <th className="pb-1 pr-3 font-semibold">Cobertura</th>
                    <th className="pb-1 font-semibold">Err.</th>
                  </tr>
                </thead>
                <tbody>
                  {(artifact.values ?? []).map((value) => (
                    <ValueRow key={value.symbol} value={value} />
                  ))}
                </tbody>
              </table>
            </CardContent>
          </Card>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card className="rounded-xl border border-border bg-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">Heatmap valor × día</CardTitle>
              </CardHeader>
              <CardContent>
                <DiaDAutoFeedbackHeatmap
                  matrix={artifact.matrix ?? []}
                  days={days}
                />
              </CardContent>
            </Card>

            <Card className="rounded-xl border border-border bg-card">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm">R acumulado por valor</CardTitle>
              </CardHeader>
              <CardContent>
                <DiaDAutoFeedbackChart
                  values={artifact.values ?? []}
                  days={days}
                />
              </CardContent>
            </Card>
          </div>

          <Card className="rounded-xl border border-border bg-card">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm">Catálogo de errores</CardTitle>
            </CardHeader>
            <CardContent>
              <DiaDAutoErrorList
                errors={artifact.errors ?? []}
                counts={artifact.summary?.errors}
              />
            </CardContent>
          </Card>

          {artifact.limits && artifact.limits.length > 0 ? (
            <Card className="rounded-xl border border-amber-500/30 bg-amber-500/5">
              <CardContent
                className="py-3"
                data-testid="dia-d-auto-feedback-limits"
              >
                <p className="text-[10px] font-semibold uppercase tracking-wide text-amber-600 dark:text-amber-400">
                  Límites declarados
                </p>
                <ul className="mt-1 space-y-0.5 text-[11px] text-muted-foreground">
                  {artifact.limits.map((limit) => (
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
