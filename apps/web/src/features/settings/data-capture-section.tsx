import { useQuery } from '@tanstack/react-query';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { api } from '@/lib/api';
import { HelpSourcesFooter } from '@/features/help/help-sources-footer';
import { SettingsSection } from '@/features/settings/settings-section';
import {
  DATA_DB_MODELS,
  DATA_FAMILIES,
  DATA_FLOW_STEPS,
  DATA_FRESHNESS_NOTES,
  DATA_INSTRUMENT_LIFECYCLE,
  DATA_MARKET_NEXT,
  DATA_MARKET_SUMMARY,
  DATA_MARKET_SYNC,
  DATA_SOURCES,
  DATA_SYNC_MODES,
  DATA_UPDATE_SCOPE,
  DATA_VALIDATION,
} from '@/features/settings/data-market-tracker';

export function DataCaptureSection({ compact = false }: { compact?: boolean }) {
  const marketQuery = useQuery({
    queryKey: ['market-providers'],
    queryFn: api.getMarketProviders,
  });

  const providers = marketQuery.data?.data ?? [];
  const yahoo = providers.find((p) => p.id === 'yahoo');
  const xtb = providers.find((p) => p.id === 'xtb');

  const body = (
    <>
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{DATA_MARKET_SUMMARY.title}</CardTitle>
          <CardDescription>Ingesta de datos · sync {DATA_MARKET_SYNC.asOf}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">{DATA_MARKET_SUMMARY.body}</p>
          <ul className="list-disc space-y-1 pl-4 text-xs text-foreground">
            {DATA_MARKET_SUMMARY.bullets.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Dos tipos de datos</CardTitle>
          <CardDescription>Técnicos vs fundamentales — qué alimenta cada uno</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {DATA_FAMILIES.map((family) => (
            <div key={family.id} className="rounded-md border border-border/70 px-3 py-2">
              <p className="text-sm font-medium text-foreground">{family.title}</p>
              <p className="mt-1 text-xs text-foreground/90">{family.plain}</p>
              <p className="mt-1.5 text-[11px] text-muted-foreground">{family.detail}</p>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Yahoo Finance</CardTitle>
            <CardDescription>Estado en vivo del proveedor primario</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {marketQuery.isLoading && <p className="text-muted-foreground">Comprobando…</p>}
            {yahoo && (
              <div className="space-y-1">
                <p className={yahoo.healthy ? 'text-emerald-400' : 'text-muted-foreground'}>
                  {yahoo.enabled
                    ? yahoo.healthy
                      ? 'Disponible'
                      : 'Configurado — sin respuesta'
                    : 'Deshabilitado'}
                </p>
                <p className="text-muted-foreground text-xs">{yahoo.message}</p>
              </div>
            )}
            <ul className="mt-3 list-disc space-y-0.5 pl-4 text-[11px] text-muted-foreground">
              {DATA_SOURCES.find((s) => s.id === 'yahoo')?.provides.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">XTB Bridge</CardTitle>
            <CardDescription>Estado en vivo del complemento opcional</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {marketQuery.isLoading && <p className="text-muted-foreground">Comprobando…</p>}
            {xtb && (
              <div className="space-y-1">
                <p className={xtb.healthy ? 'text-emerald-400' : 'text-muted-foreground'}>
                  {xtb.enabled
                    ? xtb.healthy
                      ? 'Bridge conectado'
                      : 'Configurado — offline'
                    : 'No configurado (opcional)'}
                </p>
                <p className="text-muted-foreground text-xs">{xtb.message}</p>
              </div>
            )}
            <ul className="mt-3 list-disc space-y-0.5 pl-4 text-[11px] text-muted-foreground">
              {DATA_SOURCES.find((s) => s.id === 'xtb')?.provides.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{DATA_UPDATE_SCOPE.title}</CardTitle>
          <CardDescription>Listas · cola · gráfico · rastreadores</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <p className="text-xs text-muted-foreground">{DATA_UPDATE_SCOPE.plain}</p>
          <ul className="space-y-3">
            {DATA_UPDATE_SCOPE.rows.map((row) => (
              <li key={row.who} className="rounded-md border border-border/70 px-3 py-2">
                <p className="text-sm font-medium text-foreground">{row.who}</p>
                <p className="mt-1 text-xs text-foreground/90">{row.what}</p>
                <p className="mt-1 text-[11px] text-muted-foreground">{row.when}</p>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Modos de sincronización</CardTitle>
          <CardDescription>Cómo se actualizan las velas y la ficha</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {DATA_SYNC_MODES.map((mode) => (
              <li key={mode.id} className="rounded-md border border-border/70 px-3 py-2">
                <p className="text-sm font-medium text-foreground">{mode.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">{mode.body}</p>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Validación y calidad</CardTitle>
          <CardDescription>Qué comprobamos antes y después de guardar</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {DATA_VALIDATION.map((item) => (
              <li key={item.id}>
                <p className="text-sm font-medium text-foreground">{item.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{item.body}</p>
              </li>
            ))}
          </ul>
          <div className="mt-3 space-y-1.5 border-t border-border/60 pt-3 text-xs text-muted-foreground">
            {DATA_FRESHNESS_NOTES.map((note) => (
              <p key={note.slice(0, 32)}>{note}</p>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Qué se guarda en BD</CardTitle>
          <CardDescription>
            Modelos de consulta · <code className="text-[10px]">{DATA_MARKET_SYNC.dataModel}</code>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-xs">
            {DATA_DB_MODELS.map((row) => (
              <li key={row.what} className="flex flex-col gap-0.5 sm:flex-row sm:justify-between">
                <span className="text-foreground">{row.what}</span>
                <code className="text-[10px] text-muted-foreground">{row.where}</code>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{DATA_INSTRUMENT_LIFECYCLE.title}</CardTitle>
          <CardDescription>
            Listas ↔ PostgreSQL · <code className="text-[10px]">{DATA_MARKET_SYNC.bdHint}</code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">{DATA_INSTRUMENT_LIFECYCLE.plain}</p>
          <ul className="list-disc space-y-1 pl-4 text-xs text-foreground">
            {DATA_INSTRUMENT_LIFECYCLE.bullets.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Flujo paso a paso</CardTitle>
          <CardDescription>
            Detalle operativo · ADR-002 · <code className="text-[10px]">{DATA_MARKET_SYNC.marketDoc}</code>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ol className="space-y-3 text-sm">
            {DATA_FLOW_STEPS.map((step) => (
              <li key={step.id}>
                <p className="font-medium">{step.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{step.body}</p>
              </li>
            ))}
          </ol>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Para probar ahora</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {DATA_MARKET_NEXT.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="mt-2 text-[11px] text-muted-foreground">
            Ajustes de cola: {DATA_MARKET_SYNC.configHint}. Intradía:{' '}
            <code className="text-[10px]">{DATA_MARKET_SYNC.adrIntraday}</code>
          </p>
        </CardContent>
      </Card>

      <HelpSourcesFooter sectionId="data" />
    </>
  );

  if (compact) {
    return <div className="space-y-4">{body}</div>;
  }

  return (
    <SettingsSection
      id="data-capture"
      title="Captura de datos"
      description="Cómo obtenemos y mantenemos el histórico — alimentado por data-market-tracker."
    >
      {body}
    </SettingsSection>
  );
}
