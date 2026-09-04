/**
 * Cabecera operativa Mesa · Hoy (V1.16+) — chips read-only con métricas separadas.
 */

import { useState } from "react";
import { Link } from "react-router-dom";
import type { MesaOperationalHeaderV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";
import { mesaOperationalConsoleHref } from "@/features/mesa/mesa-nav-links";

type MesaOperationalHeaderProps = {
  header: MesaOperationalHeaderV1;
};

function Chip({
  label,
  value,
  tone = "neutral",
  title,
}: {
  label: string;
  value: string;
  tone?: "neutral" | "ok" | "warn" | "bad";
  title?: string;
}) {
  return (
    <div
      className={cn(
        "rounded border px-2 py-1.5 min-w-[100px]",
        tone === "ok" && "border-emerald-500/40 bg-emerald-500/5",
        tone === "warn" && "border-amber-500/40 bg-amber-500/5",
        tone === "bad" && "border-rose-500/40 bg-rose-500/5",
        tone === "neutral" && "border-border/60 bg-muted/20",
      )}
      title={title}
    >
      <p className="text-[9px] font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-0.5 text-xs font-medium tabular-nums">{value}</p>
    </div>
  );
}

function statusTone(
  status: MesaOperationalHeaderV1["operationalStatus"],
): "ok" | "warn" | "bad" {
  if (status === "blocked") return "bad";
  if (status === "attention") return "warn";
  return "ok";
}

function freshnessTone(
  state: MesaOperationalHeaderV1["dataFreshness"]["state"],
): "ok" | "warn" | "bad" | "neutral" {
  if (state === "fresh") return "ok";
  if (state === "stale") return "warn";
  if (state === "error") return "bad";
  return "neutral";
}

function formatR(value: number | null): string {
  if (value == null) return "—";
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)} R`;
}

export function MesaOperationalHeaderStrip({
  header,
}: MesaOperationalHeaderProps) {
  const [expanded, setExpanded] = useState(false);

  const regime = header.regimeHint ?? "—";
  const capital =
    header.equity != null
      ? header.investedPct != null
        ? `${formatPrice(header.equity)} · ${header.investedPct}% inv.`
        : formatPrice(header.equity)
      : "—";

  return (
    <section
      className="space-y-2"
      data-testid="mesa-operational-header"
      aria-label="Estado operativo de la mesa"
    >
      <div className="flex flex-wrap gap-2">
        <Chip
          label="Régimen"
          value={regime}
          tone="neutral"
          title={
            regime === "—"
              ? "Régimen no disponible — no se asume operable"
              : undefined
          }
        />
        <Chip
          label="P&L cartera"
          value={formatR(header.portfolioPnLR)}
          title="P&L no realizado agregado en R"
        />
        <Chip
          label="Riesgo abierto"
          value={formatR(header.portfolioOpenRiskR)}
          title={`R si stops actuales se ejecutan · límite ${header.portfolioRiskLimitR}R`}
        />
        <Chip
          label="Stress"
          value={formatR(header.portfolioStressRiskR)}
          title="cota concurrente stops; sin correlación"
        />
        <Chip label="Capital" value={capital} />
        <Chip
          label="Datos"
          value={header.dataFreshness.label}
          tone={freshnessTone(header.dataFreshness.state)}
          title="DS-05 — no se asume frescura si el dato no está disponible; muestra parcial ≠ cartera completa"
        />
        <button
          type="button"
          className="text-left"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          <Chip
            label="Estado operativo"
            value={header.operationalStatusLabel}
            tone={statusTone(header.operationalStatus)}
            title={header.operationalPrimaryReason ?? "Click para detalle"}
          />
        </button>
        <Chip
          label="Modo"
          value={header.modeLabel}
          tone="neutral"
          title={header.modeDetail}
        />
      </div>

      {expanded ? (
        <div
          className="rounded-md border border-border/60 bg-muted/20 px-3 py-2 text-xs"
          data-testid="mesa-operational-detail"
        >
          <dl className="grid gap-1 sm:grid-cols-2">
            <div>
              <dt className="text-muted-foreground">Datos</dt>
              <dd>{header.dataFreshness.label}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Risk Gate</dt>
              <dd>
                {header.operationalStatus === "blocked" ? "Bloqueado" : "OK"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">P&L / Open / Stress</dt>
              <dd>
                {formatR(header.portfolioPnLR)} /{" "}
                {formatR(header.portfolioOpenRiskR)} /{" "}
                {formatR(header.portfolioStressRiskR)}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Límite riesgo</dt>
              <dd>{header.portfolioRiskLimitR}R</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Broker</dt>
              <dd>{header.brokerVenue ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">PAPER_D execute (env)</dt>
              <dd data-testid="mesa-paper-d-execute-env">
                {header.paperDExecuteEnv ? "ON · arm UI ≠ execute" : "OFF"}
              </dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Readiness</dt>
              <dd>{header.readinessState ?? "—"}</dd>
            </div>
            <div>
              <dt className="text-muted-foreground">Motivo</dt>
              <dd>{header.operationalPrimaryReason ?? "—"}</dd>
            </div>
          </dl>
          <Link
            to={mesaOperationalConsoleHref()}
            className="mt-2 inline-block text-primary hover:underline"
          >
            Consola operacional →
          </Link>
        </div>
      ) : null}
    </section>
  );
}
