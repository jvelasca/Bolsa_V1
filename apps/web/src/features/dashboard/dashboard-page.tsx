import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  FlaskConical,
  History,
  FileSpreadsheet,
  Landmark,
  LineChart,
  ScanSearch,
  Settings2,
  TrendingUp,
  Wallet,
} from "lucide-react";
import { Link } from "react-router-dom";
import { formatLedgerEntryLabel } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  accountTypeShortLabel,
  useActiveAccount,
} from "@/features/accounts/use-active-account";
import { HELP_CONTENT_AS_OF } from "@/features/help/help-content-as-of";
import { DataSyncSummaryCard } from "@/features/settings/data-sync-summary-card";
import { formatPrice } from "@/features/charts/chart-utils";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/stores/ui-store";

function Metric({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "positive" | "negative";
}) {
  return (
    <div className="rounded-md border border-border/60 bg-background/40 px-3 py-2">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p
        className={cn(
          "mt-0.5 text-lg font-semibold tabular-nums tracking-tight",
          tone === "positive" && "text-emerald-400",
          tone === "negative" && "text-red-400",
        )}
      >
        {value}
      </p>
      {hint ? (
        <p className="mt-0.5 text-[10px] text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}

function ActiveAccountPanel() {
  const { account, effectiveAccountId, accounts, isLoading } =
    useActiveAccount();
  const openWizard = useUiStore((s) => s.openCreateAccountWizard);

  const summaryQuery = useQuery({
    queryKey: ["account-summary", effectiveAccountId],
    queryFn: async () => {
      if (!effectiveAccountId) return null;
      return (await api.getAccountSummary(effectiveAccountId)).data;
    },
    enabled: Boolean(effectiveAccountId),
    refetchInterval: 60_000,
  });

  const summary = summaryQuery.data;
  const openAccounts = accounts.filter((a) => a.status === "active");
  const otherAccounts = openAccounts.filter((a) => a.id !== effectiveAccountId);

  return (
    <section className="rounded-lg border border-border bg-card/60 p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Cuenta activa
          </p>
          {isLoading ? (
            <p className="text-sm text-muted-foreground">Cargando cuentas…</p>
          ) : account ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <h3 className="truncate text-xl font-semibold tracking-tight">
                  {account.name}
                </h3>
                <span className="rounded border border-border px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground">
                  {accountTypeShortLabel(account.type)}
                </span>
                <span className="text-sm text-muted-foreground">
                  {account.currency}
                </span>
              </div>
              <p className="max-w-xl text-sm text-muted-foreground">
                Con esta cuenta opera toda la app (Trading, barra inferior,
                órdenes e historial). Se restaura al reabrir. Cambia o limpia
                demos en Cuentas — aquí no listamos el catálogo completo.
              </p>
            </>
          ) : (
            <p className="text-sm text-muted-foreground">
              No hay cuenta activa. Crea una demo para empezar a simular.
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            to="/accounts"
            className="inline-flex items-center gap-1 rounded-md border border-border px-3 py-1.5 text-sm hover:bg-accent"
          >
            Gestionar cuentas
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
          <button
            type="button"
            onClick={openWizard}
            className="rounded-md border border-border px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            Nueva demo
          </button>
        </div>
      </div>

      {account && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <Metric
            label="Patrimonio"
            value={summary ? formatPrice(summary.totalEquity) : "—"}
          />
          <Metric
            label="Capital disponible"
            value={summary ? formatPrice(summary.cash) : "—"}
          />
          <Metric
            label="Beneficio no realizado"
            value={summary ? formatPrice(summary.totalUnrealizedPnl) : "—"}
            tone={
              summary
                ? summary.totalUnrealizedPnl >= 0
                  ? "positive"
                  : "negative"
                : undefined
            }
          />
          <Metric
            label="Posiciones abiertas"
            value={summary ? String(summary.positionsCount) : "—"}
            hint={
              summary
                ? `Margen libre ${formatPrice(summary.freeMargin)}`
                : undefined
            }
          />
        </div>
      )}

      {otherAccounts.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-border pt-3">
          <p className="text-sm text-muted-foreground">
            {otherAccounts.length} otra
            {otherAccounts.length === 1 ? "" : "s"} cuenta
            {otherAccounts.length === 1 ? "" : "s"} activa
            {otherAccounts.length === 1 ? "" : "s"} — gestionar en Cuentas (no
            se listan aquí).
          </p>
          <Link
            to="/accounts"
            className="inline-flex items-center gap-1 rounded-md border border-border px-2.5 py-1 text-sm hover:bg-accent"
            data-testid="overview-other-accounts-link"
          >
            Ver cuentas
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}
    </section>
  );
}

function NavCard({
  title,
  description,
  icon: Icon,
  to,
  onClick,
}: {
  title: string;
  description: string;
  icon: typeof Wallet;
  to?: string;
  onClick?: () => void;
}) {
  const inner = (
    <>
      <div className="flex items-start justify-between gap-2">
        <Icon className="h-5 w-5 text-primary" />
        <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
      </div>
      <CardTitle className="mt-3 text-base">{title}</CardTitle>
      <CardDescription className="mt-1">{description}</CardDescription>
    </>
  );

  if (onClick) {
    return (
      <button type="button" onClick={onClick} className="group text-left">
        <Card className="h-full transition-colors hover:border-primary/40 hover:bg-accent/30">
          <CardHeader className="pb-2">{inner}</CardHeader>
        </Card>
      </button>
    );
  }

  return (
    <Link to={to!} className="group block">
      <Card className="h-full transition-colors hover:border-primary/40 hover:bg-accent/30">
        <CardHeader className="pb-2">{inner}</CardHeader>
      </Card>
    </Link>
  );
}

function RecentLedgerCard() {
  const { account, effectiveAccountId } = useActiveAccount();

  const ledgerQuery = useQuery({
    queryKey: ["ledger", effectiveAccountId],
    queryFn: async () => {
      if (!effectiveAccountId) return [];
      return (await api.getAccountLedger(effectiveAccountId, 8)).data;
    },
    enabled: Boolean(effectiveAccountId),
  });

  const entries = ledgerQuery.data ?? [];

  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between gap-2">
          <div>
            <CardTitle className="text-base">Últimos movimientos</CardTitle>
            <CardDescription>
              {account
                ? `Ledger de «${account.name}» (cuenta activa)`
                : "Ledger de la cuenta activa"}
            </CardDescription>
          </div>
          <Link to="/history" className="text-xs text-primary hover:underline">
            Ver historial →
          </Link>
        </div>
      </CardHeader>
      <CardContent>
        {ledgerQuery.isLoading && (
          <p className="text-sm text-muted-foreground">Cargando…</p>
        )}
        {!ledgerQuery.isLoading && entries.length === 0 && (
          <p className="text-sm text-muted-foreground">
            Sin movimientos. Cuando operes o deposites, aparecerán aquí.
          </p>
        )}
        {entries.length > 0 && (
          <ul className="space-y-2 text-sm">
            {entries.map((entry) => (
              <li
                key={entry.id}
                className="flex items-center justify-between gap-2 border-b border-border/60 pb-2 last:border-0"
              >
                <span className="min-w-0 truncate">
                  <span className="font-medium">
                    {formatLedgerEntryLabel(entry)}
                  </span>
                  {entry.symbol ? (
                    <span className="text-muted-foreground">
                      {" "}
                      · {entry.symbol}
                    </span>
                  ) : null}
                </span>
                <span
                  className={cn(
                    "shrink-0 tabular-nums",
                    entry.amount >= 0 ? "text-emerald-400" : "text-red-400",
                  )}
                >
                  {formatPrice(entry.amount)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ResearchHighlights() {
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Investigación · sync {HELP_CONTENT_AS_OF}
          </h3>
          <p className="mt-0.5 text-sm text-muted-foreground">
            Últimas mejoras: embudo Backtesting y motor de análisis fundamental
            (FIE).
          </p>
        </div>
        <p className="text-[11px] text-muted-foreground">
          Detalle en Ayuda → Backtesting / Análisis del valor
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-primary/20 bg-card/80">
          <CardHeader className="pb-2">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <FlaskConical className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">Backtesting</CardTitle>
              </div>
              <Link
                to="/backtests"
                className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
              >
                Abrir
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
            <CardDescription>
              Análisis técnico · Análisis fundamental · Play · Lista AUTO ·
              Finalistas
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <ul className="list-disc space-y-1.5 pl-4">
              <li>
                <span className="text-foreground">Análisis técnico</span>:
                gráfico, replay, equity y trades (Detalle clásico, sin FA
                mezclado).
              </li>
              <li>
                <span className="text-foreground">Análisis fundamental</span>:
                Tarjeta Valor completa (ratios, Composite, filings).
              </li>
              <li>
                <span className="text-foreground">Play</span>: genéricas → Coach
                → Lab → revalidar → Finalistas (TOP solo si el Lab mejora).
              </li>
              <li>
                <span className="text-foreground">Lista AUTO</span>: mismo ciclo
                × ticker; omitir si Finalistas frescos; progreso en el footer de
                Trading.
              </li>
              <li>
                Finalistas: <span className="text-foreground">Checklist</span> =
                paper manual (A) ·{" "}
                <span className="text-foreground">Proponer</span> = Supervisado
                F3 (C). Distintos.
              </li>
            </ul>
            <p className="text-[11px] leading-relaxed">
              No es predicción ni auto de producción. Paper D (execute) es otra
              puerta, off por defecto.
            </p>
          </CardContent>
        </Card>

        <Card className="border-primary/20 bg-card/80">
          <CardHeader className="pb-2">
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <Landmark className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">
                  Análisis fundamental
                </CardTitle>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  to="/backtests"
                  className="text-xs text-primary hover:underline"
                  title="Tarjeta Valor en Backtesting → Monitor / Valor"
                >
                  Tarjeta Valor
                </Link>
                <span className="text-muted-foreground/40">·</span>
                <Link
                  to="/screeners"
                  className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  Screeners
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
            </div>
            <CardDescription>
              FIE cerrado en código · fase prueba APP · Python calcula, LLM solo
              explica
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <ul className="list-disc space-y-1.5 pl-4">
              <li>
                <span className="text-foreground">Tarjeta Valor</span>:
                Score_FUND, Piotroski, ROIC, Beneish, Graham, DCF
                bear/base/bull, CAPM/WACC, Composite.
              </li>
              <li>
                Filings (upload / SEC / RAG) para contexto —{" "}
                <span className="text-foreground">no</span> alimentan Score_FUND
                ni el gate.
              </li>
              <li>
                Embudo FA: <span className="text-foreground">Screener FA</span>{" "}
                → whitelist → <span className="text-foreground">Paper D</span>{" "}
                (propose dry-run; execute con env).
              </li>
              <li>
                Yahoo: balance vía timeseries si el quoteSummary llega vacío;
                cobertura uneven en bancos (null-if-incomplete).
              </li>
            </ul>
            <p className="text-[11px] leading-relaxed">
              Verificar:{" "}
              <code className="rounded bg-muted px-1">pnpm test:fa</code> ·
              cobertura:{" "}
              <code className="rounded bg-muted px-1">
                pnpm audit:fa:coverage
              </code>
            </p>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

function NextStepsCard() {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Por dónde seguir</CardTitle>
        <CardDescription>
          Flujo habitual: cuenta → trading → research → paper
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm text-muted-foreground">
        <ol className="list-decimal space-y-2 pl-4">
          <li>
            Confirma la <span className="text-foreground">cuenta activa</span>{" "}
            arriba (o en la barra inferior).
          </li>
          <li>
            Abre{" "}
            <Link to="/trading" className="text-primary hover:underline">
              Trading
            </Link>{" "}
            para gráficos, listas y órdenes simuladas.
          </li>
          <li>
            En{" "}
            <Link to="/backtests" className="text-primary hover:underline">
              Backtesting
            </Link>
            : Play (o Lista AUTO) hasta Finalistas; revisa la{" "}
            <span className="text-foreground">Tarjeta Valor</span> del ticker.
          </li>
          <li>
            En{" "}
            <Link to="/screeners" className="text-primary hover:underline">
              Screeners
            </Link>
            : Screener FA → whitelist → Paper D dry-run (execute solo con{" "}
            <code className="rounded bg-muted px-1 text-[11px]">
              PAPER_D_EXECUTE=1
            </code>
            ).
          </li>
          <li>
            Revisa P&amp;L en{" "}
            <Link to="/operations" className="text-primary hover:underline">
              Operaciones
            </Link>{" "}
            o{" "}
            <Link to="/accounts" className="text-primary hover:underline">
              Cuentas
            </Link>
            .
          </li>
        </ol>
      </CardContent>
    </Card>
  );
}

export function OverviewPage() {
  const openConfig = useUiStore((s) => s.openPlatformConfig);

  const healthQuery = useQuery({
    queryKey: ["health"],
    queryFn: api.getHealth,
  });

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-2xl space-y-1">
          <h2 className="text-2xl font-semibold tracking-tight">Overview</h2>
          <p className="text-sm text-muted-foreground">
            Cuenta activa, patrimonio y atajos a Trading, Backtesting y análisis
            fundamental.
          </p>
          {healthQuery.isError && (
            <p className="mt-2 text-sm text-destructive">
              API no disponible — comprueba que el backend esté en marcha.
            </p>
          )}
        </div>
        <Link
          to="/trading"
          className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
        >
          <LineChart className="h-4 w-4" />
          Ir a Trading
        </Link>
      </div>

      <ActiveAccountPanel />

      <ResearchHighlights />

      <div>
        <h3 className="mb-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Accesos
        </h3>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <NavCard
            title="Trading"
            description="Workspace: gráficos, listas, indicadores y panel de órdenes."
            icon={LineChart}
            to="/trading"
          />
          <NavCard
            title="Backtesting"
            description="Play ciclo, Lista AUTO, Finalistas, Lab y Monitor de estado."
            icon={FlaskConical}
            to="/backtests"
          />
          <NavCard
            title="Screeners"
            description="Screener FA → whitelist · Paper D propose/execute (gated)."
            icon={ScanSearch}
            to="/screeners"
          />
          <NavCard
            title="Cuentas"
            description="Detalle, efectivo, posiciones y configuración de cada cuenta."
            icon={Wallet}
            to="/accounts"
          />
          <NavCard
            title="Operaciones"
            description="Posiciones abiertas, órdenes pendientes y P&L de la activa."
            icon={TrendingUp}
            to="/operations"
          />
          <NavCard
            title="Historial"
            description="Ledger contable, comisiones y trades ejecutados."
            icon={History}
            to="/history"
          />
          <NavCard
            title="Informe fiscal"
            description="Plusvalías realizadas (FIFO o coste medio) de la activa."
            icon={FileSpreadsheet}
            to="/fiscal"
          />
          <NavCard
            title="Configuración"
            description="Workspace, sync de datos y preferencias de la plataforma."
            icon={Settings2}
            onClick={() => openConfig("general")}
          />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <RecentLedgerCard />
        <NextStepsCard />
      </div>

      <DataSyncSummaryCard />
    </div>
  );
}
