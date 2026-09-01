/**
 * V1.60 — Tarjeta estrella DECISIÓN: PositionOperationalView canónico (GP-V160-01..03).
 * Display-only — no firma · no BUY.
 */

import { useState } from "react";
import type { PositionDto, PositionOperationalStateV1 } from "@bolsa/shared";
import {
  buildPositionDecisionFromDto,
  formatPositionDecisionPhrase,
  reconPhraseFromPortfolioStatus,
} from "@bolsa/shared";
import { cn } from "@/lib/utils";
import {
  formatPovPrimaryActionLabel,
  usePositionOperationalView,
} from "@/features/trading/use-position-operational-view";

type PositionOperationalStarCardProps = {
  position: PositionDto;
  portfolioReconStatus?: string | null;
  className?: string;
};

function SectionLabel({ children }: { children: string }) {
  return (
    <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/90">
      {children}
    </p>
  );
}

function formatOperatingStatePhrase(
  state: PositionOperationalStateV1,
  portfolioReconStatus?: string | null,
  position?: PositionDto,
): string {
  if (state === "RECONCILIATION_DRIFT") {
    return (
      reconPhraseFromPortfolioStatus(portfolioReconStatus ?? "drift") ??
      "Discrepancia de cartera · requiere acción."
    );
  }
  if (state === "RECONCILIATION_ERROR") {
    return (
      reconPhraseFromPortfolioStatus("unavailable") ??
      "Reconciliación no disponible."
    );
  }

  const decision =
    position != null
      ? buildPositionDecisionFromDto(position, { portfolioReconStatus })
      : null;
  if (decision) {
    if (state === "T2_READY" && decision.nextEvent === "T2") {
      return formatPositionDecisionPhrase(decision);
    }
    if (state === "T2_EXECUTED") {
      return "T2 ejecutado · posición parcial.";
    }
    if (state === "T1_READY" && decision.nextEvent === "T1") {
      return formatPositionDecisionPhrase(decision);
    }
    if (state === "T1_EXECUTED") {
      return "T1 ejecutado · posición parcial.";
    }
  }

  switch (state) {
    case "T2_READY":
      return "T2 disparado · pendiente de ejecutar.";
    case "T2_EXECUTED":
      return "T2 ejecutado · posición parcial.";
    case "T1_READY":
      return "T1 disparado · pendiente de ejecutar.";
    case "T1_EXECUTED":
      return "T1 ejecutado · posición parcial.";
    case "PROTECT_REQUIRED":
      return "Protección requerida · falta stop operativo.";
    case "OPEN_UNPROTECTED":
      return "Posición abierta sin protección registrada.";
    case "EXIT_REQUIRED":
      return "Salida requerida · stop alcanzado o inminente.";
    case "EXIT_PENDING":
      return "Salida pendiente de confirmación.";
    case "TRAILING":
      return "Trailing activo · stop en seguimiento.";
    case "PROTECTED":
      return "Posición protegida · stop operativo vigente.";
    case "PARTIALLY_REDUCED":
      return "Posición reducida parcialmente.";
    case "CLOSED":
      return "Posición cerrada.";
    default:
      return String(state).replace(/_/g, " ");
  }
}

function formatStopDelta(delta: number | null | undefined): string | null {
  if (delta == null || !Number.isFinite(delta)) return null;
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(2)}`;
}

export function PositionOperationalStarCard({
  position,
  portfolioReconStatus,
  className,
}: PositionOperationalStarCardProps) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const view = usePositionOperationalView(position, portfolioReconStatus);

  if (!view) return null;

  const statePhrase = formatOperatingStatePhrase(
    view.operatingState,
    portfolioReconStatus,
    position,
  );
  const actionLabel = formatPovPrimaryActionLabel(view.primaryAction);

  return (
    <div
      className={cn(
        "space-y-1.5 rounded-md border border-emerald-700/25 bg-background/50 px-2 py-1.5",
        className,
      )}
      data-testid="position-operational-star-card"
    >
      <SectionLabel>Operativa canónica</SectionLabel>
      <div
        className="space-y-0.5"
        data-testid="operativa-cockpit-pov-state"
        data-state={view.operatingState}
        data-pov-state={view.operatingState}
      >
        <p className="text-[11px] font-medium leading-snug text-foreground">
          {statePhrase}
        </p>
        <p
          className="text-[10px] text-muted-foreground"
          data-testid="operativa-cockpit-pov-action"
        >
          Acción sugerida:{" "}
          <span className="font-medium text-foreground">{actionLabel}</span>
        </p>
      </div>

      {view.stopHistory.length > 0 ? (
        <div className="border-t border-border/40 pt-1">
          <button
            type="button"
            className="text-[10px] font-medium text-foreground/90 underline-offset-2 hover:underline"
            onClick={() => setHistoryOpen((v) => !v)}
            aria-expanded={historyOpen}
            data-testid="operativa-cockpit-stop-history-toggle"
          >
            {historyOpen ? "Ocultar historial de stop" : "Historial de stop"}
          </button>
          {historyOpen ? (
            <ul
              className="mt-1 space-y-0.5 text-[10px] text-muted-foreground"
              data-testid="operativa-cockpit-stop-history"
            >
              {view.stopHistory.map((entry, idx) => (
                <li
                  key={`${entry.label}-${entry.stop}-${idx}`}
                  className="flex justify-between gap-2"
                >
                  <span className="truncate">{entry.label}</span>
                  <span className="shrink-0 font-medium tabular-nums text-foreground">
                    {entry.stop.toFixed(2)}
                    {formatStopDelta(entry.delta)
                      ? ` (${formatStopDelta(entry.delta)})`
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
