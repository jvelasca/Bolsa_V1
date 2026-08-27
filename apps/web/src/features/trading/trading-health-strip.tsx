/**
 * Línea mínima de salud operativa en el terminal Mercado (ADR-040).
 * Sin candidatos, sin cola F3, sin «Hoy», sin venue toggle.
 * Venue / kill / OE-1 viven en Hoy → estado operativo / Cuentas.
 */

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { deriveMesaRegimeHint } from "@bolsa/shared";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import {
  portfolioReconStatusFromReport,
  useOpsSelfEval,
} from "@/features/operational-console/use-ops-self-eval";
import { MESA_PATH } from "@/features/confirm/daily-nav";

type TradingHealthStripProps = {
  className?: string;
};

function okLabel(ok: boolean | null, label: string): string {
  if (ok == null) return `${label} …`;
  return ok ? `${label} OK` : `${label} !`;
}

export function TradingHealthStrip({ className }: TradingHealthStripProps) {
  const { effectiveAccountId } = useActiveAccount();

  const boardQuery = useQuery({
    queryKey: ["decision-board", effectiveAccountId, "trading-health"],
    queryFn: () => api.getDecisionBoard(effectiveAccountId!),
    enabled: Boolean(effectiveAccountId),
    staleTime: 30_000,
  });

  const killQuery = useQuery({
    queryKey: ["risk-kill-switch"],
    queryFn: () => api.getRiskKillSwitch(),
    staleTime: 15_000,
  });

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
    refetchInterval: 30_000,
    retry: 1,
  });

  const selfEvalQuery = useOpsSelfEval(effectiveAccountId);
  const board = boardQuery.data?.data;
  const regimeHint = board ? deriveMesaRegimeHint(board) : null;
  const killOn = killQuery.data?.effective === true;
  const dataOk = healthQuery.isSuccess && !healthQuery.isError;
  const recon = portfolioReconStatusFromReport(selfEvalQuery.data);
  const riskOk = !killOn && recon !== "drift";
  const accountOk = Boolean(effectiveAccountId);

  const mercadoLabel = killOn
    ? "Mercado bloqueado"
    : regimeHint
      ? `Mercado ${regimeHint}`
      : "Mercado …";

  return (
    <div
      className={cn(
        "flex shrink-0 items-center gap-3 border-b border-border bg-card/60 px-2 py-0.5 text-[11px] text-muted-foreground",
        className,
      )}
      data-testid="trading-health-strip"
      role="status"
      aria-label="Estado operativo del terminal"
    >
      <span
        className={cn(
          "font-medium",
          accountOk ? "text-foreground" : "text-amber-700 dark:text-amber-300",
        )}
      >
        {okLabel(accountOk, "Cuenta")}
      </span>
      <span aria-hidden>·</span>
      <span
        className={cn(
          "font-medium capitalize",
          killOn ? "text-rose-700 dark:text-rose-300" : "text-foreground",
        )}
      >
        {mercadoLabel}
      </span>
      <span aria-hidden>·</span>
      <span
        className={cn(
          "font-medium",
          dataOk ? "text-foreground" : "text-amber-700 dark:text-amber-300",
        )}
      >
        {okLabel(dataOk, "Datos")}
      </span>
      <span aria-hidden>·</span>
      <span
        className={cn(
          "font-medium",
          riskOk ? "text-foreground" : "text-rose-700 dark:text-rose-300",
        )}
      >
        {okLabel(riskOk, "Riesgo")}
      </span>
      <Link
        to={MESA_PATH}
        className="ml-auto shrink-0 text-primary hover:underline"
        title="Abrir Hoy — atención y oportunidades"
      >
        Hoy →
      </Link>
    </div>
  );
}
