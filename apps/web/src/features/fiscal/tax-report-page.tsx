import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { FileSpreadsheet } from "lucide-react";
import type { TaxReportSummaryDto } from "@bolsa/shared";
import { COST_BASIS_SHORT_LABELS, describeTaxProfile } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useActiveAccount } from "@/features/accounts/use-active-account";
import { formatPrice } from "@/features/charts/chart-utils";
import { absentDataLabel } from "@/components/absent-data";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useActiveAccountStore } from "@/stores/active-account-store";

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2];

function methodLabel(method: string): string {
  return (
    COST_BASIS_SHORT_LABELS[method as keyof typeof COST_BASIS_SHORT_LABELS] ??
    method
  );
}

function MethodBadge({ method }: { method: string }) {
  return (
    <span className="rounded bg-muted px-2 py-0.5 text-[10px] font-medium uppercase">
      {methodLabel(method)}
    </span>
  );
}

function SummaryMetric({
  label,
  value,
  tone,
  hint,
  testId,
}: {
  label: string;
  value: string;
  tone?: "positive" | "negative";
  hint?: string;
  testId?: string;
}) {
  return (
    <div data-testid={testId}>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "text-xl font-semibold tabular-nums",
          tone === "positive" && "text-emerald-400",
          tone === "negative" && "text-red-400",
        )}
      >
        {value}
      </p>
      {hint && <p className="text-[10px] text-muted-foreground">{hint}</p>}
    </div>
  );
}

function RealizedTable({ report }: { report: TaxReportSummaryDto }) {
  if (report.realizedLines.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Sin ventas con plusvalía/minusvalía en {report.periodLabel}.
      </p>
    );
  }

  return (
    <div
      className="overflow-x-auto"
      role="region"
      aria-label={`Plusvalías realizadas · ${report.periodLabel}`}
      tabIndex={0}
    >
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">Fecha venta</th>
            <th className="px-2 py-2 font-medium">Símbolo</th>
            <th className="px-2 py-2 text-right font-medium">Qty</th>
            <th className="px-2 py-2 text-right font-medium">Precio</th>
            <th className="px-2 py-2 text-right font-medium">Ingresos</th>
            <th className="px-2 py-2 text-right font-medium">Coste</th>
            <th className="px-2 py-2 text-right font-medium">Resultado</th>
          </tr>
        </thead>
        <tbody>
          {report.realizedLines.map((line) => (
            <tr
              key={line.id}
              className="border-b border-border/50 hover:bg-accent/20"
            >
              <td className="px-2 py-2 whitespace-nowrap text-xs text-muted-foreground">
                {formatDate(line.executedAt)}
              </td>
              <td className="px-2 py-2 font-medium">{line.symbol}</td>
              <td className="px-2 py-2 text-right tabular-nums">
                {line.quantity}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {formatPrice(line.sellPrice, report.currency)}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {formatPrice(line.proceeds, report.currency)}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {formatPrice(line.costBasis, report.currency)}
              </td>
              <td
                className={cn(
                  "px-2 py-2 text-right tabular-nums font-medium",
                  line.realizedGain >= 0 ? "text-emerald-400" : "text-red-400",
                )}
              >
                {formatPrice(line.realizedGain, report.currency)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {report.method === "fifo" &&
        report.realizedLines.some((l) => l.acquisitionDates.length > 0) && (
          <p className="mt-2 text-[10px] text-muted-foreground">
            FIFO: el coste de cada venta corresponde a los lotes más antiguos
            (incluye comisiones en compra y resta comisiones en venta).
          </p>
        )}
    </div>
  );
}

function UnrealizedTable({ report }: { report: TaxReportSummaryDto }) {
  if (report.unrealizedLines.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">Sin posiciones abiertas.</p>
    );
  }

  return (
    <div
      className="overflow-x-auto"
      role="region"
      aria-label={`Posiciones abiertas · ${report.periodLabel}`}
      tabIndex={0}
    >
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">Símbolo</th>
            <th className="px-2 py-2 text-right font-medium">Qty</th>
            <th className="px-2 py-2 text-right font-medium">Coste medio</th>
            <th className="px-2 py-2 text-right font-medium">Precio</th>
            <th className="px-2 py-2 text-right font-medium">
              P&amp;L no realizado
            </th>
          </tr>
        </thead>
        <tbody>
          {report.unrealizedLines.map((line) => (
            <tr
              key={line.instrumentId}
              className="border-b border-border/50 hover:bg-accent/20"
            >
              <td className="px-2 py-2 font-medium">{line.symbol}</td>
              <td className="px-2 py-2 text-right tabular-nums">
                {line.quantity}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {formatPrice(line.avgCost, report.currency)}
              </td>
              <td className="px-2 py-2 text-right tabular-nums">
                {line.marketPrice != null
                  ? formatPrice(line.marketPrice, report.currency)
                  : absentDataLabel()}
              </td>
              <td
                className={cn(
                  "px-2 py-2 text-right tabular-nums",
                  line.unrealizedGain != null && line.unrealizedGain >= 0
                    ? "text-emerald-400"
                    : "text-red-400",
                )}
              >
                {line.unrealizedGain != null
                  ? formatPrice(line.unrealizedGain, report.currency)
                  : absentDataLabel()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TaxReportPage() {
  const [year, setYear] = useState(CURRENT_YEAR);
  const setActiveAccountId = useActiveAccountStore((s) => s.setActiveAccountId);
  const {
    account,
    effectiveAccountId,
    isLoading: accountsLoading,
  } = useActiveAccount();

  const accountsQuery = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.getAccounts()).data,
  });
  const accounts = accountsQuery.data ?? [];

  const reportQuery = useQuery({
    queryKey: ["tax-report", effectiveAccountId, year],
    queryFn: async () => {
      if (!effectiveAccountId) return null;
      return (await api.getTaxReport(effectiveAccountId, year)).data;
    },
    enabled: Boolean(effectiveAccountId),
  });

  const report = reportQuery.data;
  const projectedRate = account?.settings?.tax.capitalGainsTaxPct ?? null;
  // COM-D10: deep-link a la ficha de cuenta con la pestaña Config y el bloque fiscal
  // ya seleccionado, en vez de mandar al usuario a buscar el botón de edición.
  const editFiscalHref = effectiveAccountId
    ? `/accounts?selected=${encodeURIComponent(effectiveAccountId)}&tab=config&focus=fiscal`
    : "/accounts";

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <FileSpreadsheet className="h-6 w-6 text-primary" />
            Informe fiscal
          </h1>
          <p className="text-sm text-muted-foreground">
            Plusvalías realizadas y posiciones abiertas — simulación según
            perfil de la cuenta.
          </p>
        </div>
        <Link to="/overview" className="text-sm text-primary hover:underline">
          ← Overview
        </Link>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle level="h2" className="text-base">
            Parámetros
          </CardTitle>
          <CardDescription>
            El método de coste y la jurisdicción salen del perfil fiscal de la
            cuenta; aquí solo eliges qué ejercicio mirar.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex min-w-[240px] flex-col gap-1 text-sm">
              <span className="text-muted-foreground">
                Cuenta activa de la app
              </span>
              <select
                value={effectiveAccountId ?? ""}
                onChange={(e) => setActiveAccountId(e.target.value || null)}
                className="rounded-md border border-border bg-background px-3 py-2"
                disabled={accountsLoading}
                data-testid="fiscal-account-select"
              >
                {accounts.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name} ({a.currency})
                  </option>
                ))}
              </select>
              <span className="text-[11px] text-muted-foreground">
                Cambiar de cuenta aquí cambia también la cuenta con la que opera
                la app.
              </span>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Ejercicio</span>
              <select
                value={year}
                onChange={(e) => setYear(Number(e.target.value))}
                className="rounded-md border border-border bg-background px-3 py-2"
                data-testid="fiscal-year-select"
              >
                {YEAR_OPTIONS.map((y) => (
                  <option key={y} value={y}>
                    {y}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {account?.settings ? (
            <div className="rounded-md border border-border bg-muted/20 p-3 text-xs">
              <p className="flex flex-wrap items-center gap-2">
                <span className="font-medium">Perfil fiscal aplicado</span>
                <MethodBadge method={account.settings.tax.costBasisMethod} />
              </p>
              <p className="mt-1 text-muted-foreground">
                {describeTaxProfile(account.settings.tax)}
              </p>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1">
                <span className="text-muted-foreground">
                  Comisión de operación:{" "}
                  <span className="text-foreground">
                    {account.settings.commission.label}
                  </span>
                </span>
                <Link
                  to={editFiscalHref}
                  className="text-primary hover:underline"
                  data-testid="fiscal-edit-profile-link"
                >
                  Editar perfil fiscal →
                </Link>
              </div>
            </div>
          ) : null}
        </CardContent>
      </Card>

      {accountsLoading && (
        <p className="text-sm text-muted-foreground">Cargando cuentas…</p>
      )}

      {!accountsLoading && !effectiveAccountId && (
        <p className="text-sm text-muted-foreground">
          No hay cuenta activa. Crea una demo en Cuentas para generar el
          informe.
        </p>
      )}

      {reportQuery.isLoading && (
        <p className="text-sm text-muted-foreground">Calculando informe…</p>
      )}

      {reportQuery.isError && (
        <p className="text-sm text-destructive" data-testid="fiscal-error">
          No se pudo generar el informe fiscal
          {reportQuery.error instanceof Error && reportQuery.error.message
            ? `: ${reportQuery.error.message}`
            : "."}
        </p>
      )}

      {report && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  label="Resultado neto realizado"
                  value={formatPrice(report.netRealizedGain, report.currency)}
                  tone={report.netRealizedGain >= 0 ? "positive" : "negative"}
                  hint={report.periodLabel}
                  testId="fiscal-net-realized"
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  label="Plusvalías"
                  value={formatPrice(report.totalGains, report.currency)}
                  tone="positive"
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  label="Minusvalías"
                  value={formatPrice(report.totalLosses, report.currency)}
                  tone="negative"
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  // COM-D3: el backend (F-FIN-2) suma SOLO las fees del ejercicio y
                  // excluye la custodia. La etiqueta anterior («Histórico acumulado»)
                  // describía otra magnitud.
                  label="Comisiones de operaciones"
                  value={formatPrice(report.feesPaidTotal, report.currency)}
                  hint={`${report.periodLabel} · sin custodia`}
                  testId="fiscal-fees"
                />
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {report.estimatedTaxLiability != null && (
              <Card
                className="border-amber-500/30 bg-amber-500/5"
                data-testid="fiscal-estimated-tax-card"
              >
                <CardContent className="space-y-1 pt-4">
                  <SummaryMetric
                    label="Impuesto estimado sobre plusvalías"
                    value={formatPrice(
                      report.estimatedTaxLiability,
                      report.currency,
                    )}
                    hint={
                      projectedRate != null
                        ? `${methodLabel(report.method)} · tipo ${projectedRate} % sobre el neto realizado · proyección, no retención`
                        : `${methodLabel(report.method)} · proyección, no retención`
                    }
                    testId="fiscal-estimated-tax"
                  />
                  <p className="text-[10px] text-muted-foreground">
                    El IRPF del ahorro en España es progresivo (19 / 21 / 23 /
                    27 / 28 % por tramos): aquí se aplica un tipo único como
                    orientación, no como liquidación.
                  </p>
                </CardContent>
              </Card>
            )}

            {report.totalUnrealizedGain != null && (
              <Card>
                <CardContent className="pt-4">
                  <SummaryMetric
                    label="P&amp;L no realizado (posiciones abiertas)"
                    value={formatPrice(
                      report.totalUnrealizedGain,
                      report.currency,
                    )}
                    tone={
                      report.totalUnrealizedGain >= 0 ? "positive" : "negative"
                    }
                    hint={`${report.openPositionCount} posiciones · no tributa hasta la venta`}
                    testId="fiscal-unrealized-total"
                  />
                </CardContent>
              </Card>
            )}
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Plusvalías realizadas</CardTitle>
              <CardDescription>
                Ventas en {report.periodLabel} · método{" "}
                {report.method === "fifo" ? "FIFO" : "coste medio ponderado"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RealizedTable report={report} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Posiciones abiertas (referencia)
              </CardTitle>
              <CardDescription>
                No tributan hasta la venta — informativo
              </CardDescription>
            </CardHeader>
            <CardContent>
              <UnrealizedTable report={report} />
            </CardContent>
          </Card>

          <p className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-muted-foreground">
            Simulación con fines informativos. No sustituye asesoramiento
            fiscal. Las comisiones se imputan desde el historial de movimientos
            de las operaciones (la custodia no cuenta como comisión de
            operación); la retención de dividendos (
            {report.dividendWithholdingPct} %) se aplicará en fase posterior
            cuando se registren dividendos.
          </p>
        </>
      )}
    </div>
  );
}
