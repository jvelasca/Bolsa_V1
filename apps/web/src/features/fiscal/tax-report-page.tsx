import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { FileSpreadsheet } from 'lucide-react';
import type { TaxReportSummaryDto } from '@bolsa/shared';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useActiveAccount } from '@/features/accounts/use-active-account';
import { formatPrice } from '@/features/charts/chart-utils';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { useActiveAccountStore } from '@/stores/active-account-store';

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = [CURRENT_YEAR, CURRENT_YEAR - 1, CURRENT_YEAR - 2];

function MethodBadge({ method }: { method: string }) {
  return (
    <span className="rounded bg-muted px-2 py-0.5 text-[10px] font-medium uppercase">
      {method === 'fifo' ? 'FIFO' : 'Coste medio'}
    </span>
  );
}

function SummaryMetric({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone?: 'positive' | 'negative';
  hint?: string;
}) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          'text-xl font-semibold tabular-nums',
          tone === 'positive' && 'text-emerald-400',
          tone === 'negative' && 'text-red-400',
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
    <div className="overflow-x-auto">
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
            <tr key={line.id} className="border-b border-border/50 hover:bg-accent/20">
              <td className="px-2 py-2 whitespace-nowrap text-xs text-muted-foreground">
                {new Date(line.executedAt).toLocaleDateString('es-ES')}
              </td>
              <td className="px-2 py-2 font-medium">{line.symbol}</td>
              <td className="px-2 py-2 text-right tabular-nums">{line.quantity}</td>
              <td className="px-2 py-2 text-right tabular-nums">{formatPrice(line.sellPrice)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{formatPrice(line.proceeds)}</td>
              <td className="px-2 py-2 text-right tabular-nums">{formatPrice(line.costBasis)}</td>
              <td
                className={cn(
                  'px-2 py-2 text-right tabular-nums font-medium',
                  line.realizedGain >= 0 ? 'text-emerald-400' : 'text-red-400',
                )}
              >
                {formatPrice(line.realizedGain)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {report.method === 'fifo' && report.realizedLines.some((l) => l.acquisitionDates.length > 0) && (
        <p className="mt-2 text-[10px] text-muted-foreground">
          FIFO: el coste de cada venta corresponde a los lotes más antiguos (incluye comisiones en
          compra y resta comisiones en venta).
        </p>
      )}
    </div>
  );
}

function UnrealizedTable({ report }: { report: TaxReportSummaryDto }) {
  if (report.unrealizedLines.length === 0) {
    return <p className="text-sm text-muted-foreground">Sin posiciones abiertas.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left text-xs text-muted-foreground">
            <th className="px-2 py-2 font-medium">Símbolo</th>
            <th className="px-2 py-2 text-right font-medium">Qty</th>
            <th className="px-2 py-2 text-right font-medium">Coste medio</th>
            <th className="px-2 py-2 text-right font-medium">Precio</th>
            <th className="px-2 py-2 text-right font-medium">P&amp;L no realizado</th>
          </tr>
        </thead>
        <tbody>
          {report.unrealizedLines.map((line) => (
            <tr key={line.instrumentId} className="border-b border-border/50 hover:bg-accent/20">
              <td className="px-2 py-2 font-medium">{line.symbol}</td>
              <td className="px-2 py-2 text-right tabular-nums">{line.quantity}</td>
              <td className="px-2 py-2 text-right tabular-nums">{formatPrice(line.avgCost)}</td>
              <td className="px-2 py-2 text-right tabular-nums">
                {line.marketPrice != null ? formatPrice(line.marketPrice) : '—'}
              </td>
              <td
                className={cn(
                  'px-2 py-2 text-right tabular-nums',
                  line.unrealizedGain != null && line.unrealizedGain >= 0
                    ? 'text-emerald-400'
                    : 'text-red-400',
                )}
              >
                {line.unrealizedGain != null ? formatPrice(line.unrealizedGain) : '—'}
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
  const { account, effectiveAccountId, isLoading: accountsLoading } = useActiveAccount();

  const accountsQuery = useQuery({
    queryKey: ['accounts'],
    queryFn: async () => (await api.getAccounts()).data,
  });
  const accounts = accountsQuery.data ?? [];

  const reportQuery = useQuery({
    queryKey: ['tax-report', effectiveAccountId, year],
    queryFn: async () => {
      if (!effectiveAccountId) return null;
      return (await api.getTaxReport(effectiveAccountId, year)).data;
    },
    enabled: Boolean(effectiveAccountId),
  });

  const report = reportQuery.data;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            <FileSpreadsheet className="h-6 w-6 text-primary" />
            Informe fiscal
          </h2>
          <p className="text-sm text-muted-foreground">
            Plusvalías realizadas y posiciones abiertas — simulación según perfil de la cuenta.
          </p>
        </div>
        <Link to="/overview" className="text-sm text-primary hover:underline">
          ← Overview
        </Link>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base">Parámetros</CardTitle>
          <CardDescription>
            Método de coste y jurisdicción definidos en la cuenta ·{' '}
            <Link to="/accounts" className="text-primary hover:underline">
              editar perfil fiscal
            </Link>
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-end gap-4">
          <label className="flex min-w-[200px] flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Cuenta</span>
            <select
              value={effectiveAccountId ?? ''}
              onChange={(e) => setActiveAccountId(e.target.value || null)}
              className="rounded-md border border-border bg-background px-3 py-2"
              disabled={accountsLoading}
            >
              {accounts.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name} ({a.currency})
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            <span className="text-muted-foreground">Ejercicio</span>
            <select
              value={year}
              onChange={(e) => setYear(Number(e.target.value))}
              className="rounded-md border border-border bg-background px-3 py-2"
            >
              {YEAR_OPTIONS.map((y) => (
                <option key={y} value={y}>
                  {y}
                </option>
              ))}
            </select>
          </label>
          {account?.settings && (
            <div className="text-sm">
              <p className="text-xs text-muted-foreground">Perfil fiscal</p>
              <p className="flex items-center gap-2">
                {account.settings.tax.jurisdiction}
                <MethodBadge method={account.settings.tax.costBasisMethod} />
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {reportQuery.isLoading && (
        <p className="text-sm text-muted-foreground">Calculando informe…</p>
      )}

      {reportQuery.isError && (
        <p className="text-sm text-destructive">No se pudo generar el informe fiscal.</p>
      )}

      {report && (
        <>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  label="Resultado neto realizado"
                  value={formatPrice(report.netRealizedGain)}
                  tone={report.netRealizedGain >= 0 ? 'positive' : 'negative'}
                  hint={report.periodLabel}
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  label="Plusvalías"
                  value={formatPrice(report.totalGains)}
                  tone="positive"
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  label="Minusvalías"
                  value={formatPrice(report.totalLosses)}
                  tone="negative"
                />
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  label="Comisiones pagadas"
                  value={formatPrice(report.feesPaidTotal)}
                  hint="Histórico acumulado"
                />
              </CardContent>
            </Card>
          </div>

          {report.totalUnrealizedGain != null && (
            <Card>
              <CardContent className="pt-4">
                <SummaryMetric
                  label="P&amp;L no realizado (posiciones abiertas)"
                  value={formatPrice(report.totalUnrealizedGain)}
                  tone={report.totalUnrealizedGain >= 0 ? 'positive' : 'negative'}
                  hint={`${report.openPositionCount} posiciones`}
                />
              </CardContent>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Plusvalías realizadas</CardTitle>
              <CardDescription>
                Ventas en {report.periodLabel} · método{' '}
                {report.method === 'fifo' ? 'FIFO' : 'coste medio ponderado'}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <RealizedTable report={report} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Posiciones abiertas (referencia)</CardTitle>
              <CardDescription>No tributan hasta la venta — informativo</CardDescription>
            </CardHeader>
            <CardContent>
              <UnrealizedTable report={report} />
            </CardContent>
          </Card>

          <p className="rounded-md border border-amber-500/30 bg-amber-500/5 p-3 text-xs text-muted-foreground">
            Simulación con fines informativos. No sustituye asesoramiento fiscal. Las comisiones se
            imputan desde el ledger; retención dividendos ({report.dividendWithholdingPct} %) aplicará
            en fase posterior cuando se registren dividendos.
          </p>
        </>
      )}
    </div>
  );
}
