/**
 * Tira Hoy — compresión Decision Board + cola F3 en la mesa (ADR-031).
 * No es una sexta puerta: resume y abre el drawer Confirmar.
 */

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type {
  ExitRadarV1,
  ExpectancyV1,
  HoyQueueItemV1,
  HoySetupEvidenceV1,
  MfeMaeV1,
  ProtectPlanV1,
  ThesisHealthV1,
} from "@bolsa/shared";
import { mapDecisionBoardToHoyQueue } from "@bolsa/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { CONFIRM_PATH } from "@/features/confirm/confirm-nav";
import { openConfirmDrawer } from "@/features/confirm/confirm-drawer";

const KIND_CLASS: Record<HoyQueueItemV1["kind"], string> = {
  BUY: "bg-emerald-500/15 text-emerald-800 dark:text-emerald-200",
  ARMED: "bg-sky-500/15 text-sky-800 dark:text-sky-200",
  WATCH: "bg-amber-500/15 text-amber-900 dark:text-amber-200",
  REVIEW: "bg-orange-500/15 text-orange-900 dark:text-orange-200",
  BLOCKED: "bg-rose-500/15 text-rose-800 dark:text-rose-200",
};

function whyLabel(code: string): string {
  switch (code) {
    case "fit":
      return "No encaja en la cartera";
    case "entry":
      return "Entrada aún no lista";
    case "freshness":
      return "Datos no frescos";
    case "mandate":
      return "Sin mandato abierto";
    case "expired":
      return "La decisión caducó";
    case "no_stop":
      return "Falta stop estructural";
    case "regime":
      return "Régimen no admite longs";
    case "orphan":
      return "Sin paquete de decisión";
    case "rr":
      return "Riesgo/beneficio insuficiente";
    default:
      return code;
  }
}

function setupLine(setup: HoySetupEvidenceV1): string {
  const parts: string[] = [];
  if (setup.entrySetup && setup.entrySetup !== "none") {
    parts.push(setup.entrySetup);
  } else if (setup.entrySetup === "none") {
    parts.push("none");
  }
  if (setup.phase && setup.phase !== "none") {
    parts.push(`fase ${setup.phase}`);
  }
  if (setup.effort && setup.effort !== "none") {
    parts.push(setup.effort.replaceAll("_", " "));
  }
  return parts.length > 0 ? parts.join(" · ") : "—";
}

function thesisHealthLine(health: ThesisHealthV1): string {
  const parts = [health.hint];
  if (health.why.length > 0) {
    parts.push(health.why.join(", "));
  }
  return parts.join(" · ");
}

function protectPlanLine(plan: ProtectPlanV1): string {
  const parts: string[] = [];
  if (plan.rMultiple != null) {
    parts.push(`${plan.rMultiple}R`);
  }
  if (plan.target1 != null) {
    parts.push(`T1 ${plan.target1}`);
  }
  if (plan.suggestedProtectStop != null) {
    parts.push(`proteger @ ${plan.suggestedProtectStop}`);
  }
  return parts.length > 0 ? parts.join(" · ") : "—";
}

function exitRadarLine(radar: ExitRadarV1): string {
  const parts = [radar.status.replaceAll("_", " ")];
  if (radar.rMultiple != null) parts.push(`${radar.rMultiple}R`);
  if (radar.suggestedTrailStop != null) {
    parts.push(`trail @ ${radar.suggestedTrailStop}`);
  }
  if (radar.why.length > 0) parts.push(radar.why.join(", "));
  return parts.join(" · ");
}

function mfeMaeLine(metrics: MfeMaeV1): string {
  const parts: string[] = [];
  if (metrics.mfeR != null) parts.push(`MFE ${metrics.mfeR}R`);
  if (metrics.maeR != null) parts.push(`MAE ${metrics.maeR}R`);
  if (metrics.status !== "observe") {
    parts.push(metrics.status);
  }
  return parts.length > 0 ? parts.join(" · ") : "—";
}

function expectancyLine(exp: ExpectancyV1): string {
  const parts: string[] = [];
  if (exp.entrySetup) parts.push(exp.entrySetup);
  if (exp.expectancyR != null) parts.push(`E ${exp.expectancyR}R`);
  parts.push(`n=${exp.n}`);
  if (exp.winRate != null) parts.push(`WR ${(exp.winRate * 100).toFixed(0)}%`);
  if (exp.status === "thin") parts.push("thin");
  parts.push("≠ permiso");
  return parts.join(" · ");
}

export function HoyCommandStrip() {
  const { effectiveAccountId } = useActiveAccount();
  const [selected, setSelected] = useState<HoyQueueItemV1 | null>(null);
  const query = useQuery({
    queryKey: ["decision-board", effectiveAccountId, "hoy"],
    enabled: Boolean(effectiveAccountId),
    queryFn: async () => {
      const res = await api.getDecisionBoard(effectiveAccountId as string);
      return res.data;
    },
    staleTime: 30_000,
  });

  const items = useMemo(
    () => (query.data ? mapDecisionBoardToHoyQueue(query.data) : []),
    [query.data],
  );
  const pending = query.data?.buckets.pendingConfirm ?? 0;

  return (
    <div
      data-testid="hoy-command-strip"
      className="flex shrink-0 items-center gap-2 border-b border-border bg-card/80 px-2 py-1 text-xs"
    >
      <span className="shrink-0 font-semibold uppercase tracking-wide text-muted-foreground">
        Hoy
      </span>
      {query.isLoading ? (
        <span className="text-muted-foreground">Cargando cola…</span>
      ) : items.length === 0 ? (
        <span className="text-muted-foreground">
          0 operaciones accionables — puede ser una buena decisión.
        </span>
      ) : (
        <ul className="flex min-w-0 flex-1 flex-wrap items-center gap-1">
          {items.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                data-testid={`hoy-item-${item.symbol}`}
                className={cn(
                  "rounded px-1.5 py-0.5 font-medium tabular-nums",
                  KIND_CLASS[item.kind],
                )}
                onClick={() => setSelected(item)}
              >
                {item.kind} {item.symbol}
              </button>
            </li>
          ))}
        </ul>
      )}
      <span className="ml-auto shrink-0 text-muted-foreground">
        Firma {pending}
      </span>
      <button
        type="button"
        className="shrink-0 rounded border border-border px-1.5 py-0.5 hover:bg-muted"
        onClick={() => openConfirmDrawer()}
      >
        Firmar
      </button>

      {selected ? (
        <div
          className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 sm:items-center"
          role="dialog"
          aria-labelledby="hoy-package-title"
        >
          <div className="w-full max-w-md rounded-lg border border-border bg-card p-4 shadow-lg">
            <h2 id="hoy-package-title" className="text-sm font-semibold">
              {selected.symbol} · {selected.kind}
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Gate {selected.gate} · estado {selected.status}
            </p>
            {selected.setup ? (
              <div className="mt-3" data-testid="hoy-setup">
                <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                  Setup
                </p>
                <p className="mt-1 text-sm">{setupLine(selected.setup)}</p>
              </div>
            ) : null}
            {selected.mfeMae && selected.mfeMae.status !== "none" ? (
              <div className="mt-3" data-testid="hoy-mfe-mae">
                <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                  Excursión
                </p>
                <p className="mt-1 text-sm tabular-nums">
                  {mfeMaeLine(selected.mfeMae)}
                </p>
              </div>
            ) : null}
            {selected.expectancy && selected.expectancy.status !== "none" ? (
              <div className="mt-3" data-testid="hoy-expectancy">
                <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                  Expectativa
                </p>
                <p className="mt-1 text-sm tabular-nums">
                  {expectancyLine(selected.expectancy)}
                </p>
              </div>
            ) : null}
            {selected.thesisHealth?.status === "review" ? (
              <div className="mt-3" data-testid="hoy-thesis-review">
                <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                  Revisar tesis
                </p>
                <p className="mt-1 text-sm">
                  {thesisHealthLine(selected.thesisHealth)}
                </p>
              </div>
            ) : null}
            {selected.protectPlan?.status === "protect_hint" ? (
              <div className="mt-3" data-testid="hoy-protect">
                <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                  Proteger
                </p>
                <p className="mt-1 text-sm">
                  {protectPlanLine(selected.protectPlan)}
                </p>
              </div>
            ) : null}
            {selected.exitRadar && selected.exitRadar.status !== "none" ? (
              <div className="mt-3" data-testid="hoy-exit-radar">
                <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                  Salida
                </p>
                <p className="mt-1 text-sm">
                  {exitRadarLine(selected.exitRadar)}
                </p>
              </div>
            ) : null}
            <div className="mt-3">
              <p className="text-[10px] font-semibold uppercase text-muted-foreground">
                Why not
              </p>
              {selected.whyNot.length === 0 ? (
                <p className="text-sm">Lista para firmar en Confirmar.</p>
              ) : (
                <ul className="mt-1 list-disc pl-4 text-sm">
                  {selected.whyNot.map((code) => (
                    <li key={code}>{whyLabel(code)}</li>
                  ))}
                </ul>
              )}
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <button
                type="button"
                className="rounded bg-primary px-2 py-1 text-xs text-primary-foreground"
                onClick={() => {
                  openConfirmDrawer();
                  setSelected(null);
                }}
              >
                Firmar
              </button>
              <Link
                to={CONFIRM_PATH}
                className="rounded border border-border px-2 py-1 text-xs"
                onClick={() => setSelected(null)}
              >
                Abrir Confirmar
              </Link>
              <button
                type="button"
                className="ml-auto text-xs text-muted-foreground"
                onClick={() => setSelected(null)}
              >
                Cerrar
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
