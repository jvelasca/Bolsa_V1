/**
 * Cabecera operativa Mesa · Hoy (V1.16+) — chips read-only con métricas separadas.
 */

import { Link } from "react-router-dom";
import type { MesaOperationalHeaderV1 } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { formatPrice } from "@/features/charts/chart-utils";
import { absentDataLabel } from "@/components/absent-data";
import { TechnicalDetail } from "@/components/technical-detail";
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
  if (value == null) return absentDataLabel();
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)} R`;
}

export function MesaOperationalHeaderStrip({
  header,
}: MesaOperationalHeaderProps) {
  const regime = header.regimeHint ?? absentDataLabel();
  const capital =
    header.equity != null
      ? header.investedPct != null
        ? `${formatPrice(header.equity)} · ${header.investedPct}% inv.`
        : formatPrice(header.equity)
      : absentDataLabel();

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
            header.regimeHint == null
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
        <Chip
          label="Estado operativo"
          value={header.operationalStatusLabel}
          tone={statusTone(header.operationalStatus)}
          title={header.operationalPrimaryReason ?? undefined}
        />
        <Chip
          label="Modo"
          value={header.modeLabel}
          tone="neutral"
          title={header.modeDetail}
        />
      </div>

      <TechnicalDetail testId="mesa-operational-detail">
        <dl className="grid gap-1 sm:grid-cols-2">
          <div>
            <dt className="text-muted-foreground">Datos</dt>
            <dd>{header.dataFreshness.label}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Control de riesgo</dt>
            <dd>
              {header.operationalStatus === "blocked"
                ? "Bloqueado"
                : "Sin bloqueos"}
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
            <dd>{header.brokerVenue ?? absentDataLabel()}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">
              Ejecución automática (entorno)
            </dt>
            <dd data-testid="mesa-paper-d-execute-env">
              {header.paperDExecuteEnv
                ? "Disponible · no ejecuta por sí sola"
                : "Desactivada"}
            </dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Preparación</dt>
            <dd>{header.readinessState ?? absentDataLabel()}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Motivo</dt>
            <dd>{header.operationalPrimaryReason ?? absentDataLabel()}</dd>
          </div>
        </dl>
        <Link
          to={mesaOperationalConsoleHref()}
          className="mt-2 inline-block text-primary hover:underline"
        >
          Consola operacional →
        </Link>
      </TechnicalDetail>
    </section>
  );
}
