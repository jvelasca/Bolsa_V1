/**
 * Ayuda → Análisis del valor — pedagogía Facts/Assessments/Session/pesos + Replay
 * + inventario FIE y checklist de prueba (fase optimización 2026-07-31).
 */

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { HelpSourcesFooter } from '@/features/help/help-sources-footer';
import { DecisionReplayPanel } from '@/features/settings/decision-replay-panel';
import {
  VALUE_ANALYSIS_DB,
  VALUE_ANALYSIS_FA_INVENTORY,
  VALUE_ANALYSIS_LAYERS,
  VALUE_ANALYSIS_NEXT,
  VALUE_ANALYSIS_PRINCIPLE,
  VALUE_ANALYSIS_SYNC,
  VALUE_ANALYSIS_TEST_CHECKLIST,
  VALUE_ANALYSIS_WEIGHT_TABLE,
  VALUE_ANALYSIS_YOU_ARE_HERE,
} from '@/features/settings/value-analysis-tracker';

export function ValueAnalysisSection({
  initialSessionId,
}: {
  initialSessionId?: string | null;
} = {}) {
  return (
    <div className="space-y-4">
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{VALUE_ANALYSIS_YOU_ARE_HERE.title}</CardTitle>
          <CardDescription>Orientación operativa · sync {VALUE_ANALYSIS_SYNC.asOf}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          <p className="text-xs text-muted-foreground">{VALUE_ANALYSIS_YOU_ARE_HERE.body}</p>
          <ol className="list-decimal space-y-1 pl-4 text-xs text-foreground">
            {VALUE_ANALYSIS_YOU_ARE_HERE.steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
          <p className="text-[11px] text-muted-foreground">{VALUE_ANALYSIS_YOU_ARE_HERE.pause}</p>
          <p className="text-[10px] text-muted-foreground">
            Doc: <code>{VALUE_ANALYSIS_SYNC.docRef}</code>
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Inventario FA (FIE)</CardTitle>
          <CardDescription>Entregado en código · listo para prueba en APP</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-1.5 sm:grid-cols-2">
            {VALUE_ANALYSIS_FA_INVENTORY.map((row) => (
              <li
                key={row.id}
                className="rounded-md border border-border/60 px-2 py-1.5 text-[11px]"
              >
                <span className="font-medium text-foreground">{row.label}</span>
                <span className="mt-0.5 block text-muted-foreground">{row.detail}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Checklist de prueba</CardTitle>
          <CardDescription>Usar al validar refresh, UI, Screeners y Paper D</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {VALUE_ANALYSIS_TEST_CHECKLIST.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Análisis del valor</CardTitle>
          <CardDescription>
            Lecturas multimodales y auditabilidad · sync {VALUE_ANALYSIS_SYNC.asOf}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          <div className="rounded-md border border-border bg-muted/20 px-3 py-2">
            <p className="text-xs font-medium text-foreground">{VALUE_ANALYSIS_PRINCIPLE.title}</p>
            <p className="mt-1 text-xs text-muted-foreground">{VALUE_ANALYSIS_PRINCIPLE.body}</p>
          </div>
          <ul className="space-y-3">
            {VALUE_ANALYSIS_LAYERS.map((layer) => (
              <li key={layer.id} className="rounded-md border border-border/70 px-3 py-2">
                <p className="text-sm font-medium text-foreground">{layer.title}</p>
                <p className="mt-1 text-xs text-muted-foreground">{layer.body}</p>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Decision Replay</CardTitle>
          <CardDescription>
            Caja negra: contexto → assessments → pesos → runtime → recommendation → gate → outcome
          </CardDescription>
        </CardHeader>
        <CardContent>
          <DecisionReplayPanel initialSessionId={initialSessionId} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">WeightRules (orden de magnitud)</CardTitle>
          <CardDescription>Matriz base; el régimen (crisis/risk_off) la reajusta</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-border text-muted-foreground">
                  <th className="py-1.5 pr-2 font-medium">Horizonte</th>
                  <th className="py-1.5 pr-2 font-medium">TA</th>
                  <th className="py-1.5 pr-2 font-medium">FUND</th>
                  <th className="py-1.5 pr-2 font-medium">Macro</th>
                  <th className="py-1.5 font-medium">News</th>
                </tr>
              </thead>
              <tbody>
                {VALUE_ANALYSIS_WEIGHT_TABLE.map((row) => (
                  <tr key={row.horizon} className="border-b border-border/50">
                    <td className="py-1.5 pr-2 text-foreground">{row.horizon}</td>
                    <td className="py-1.5 pr-2 text-muted-foreground">{row.ta}</td>
                    <td className="py-1.5 pr-2 text-muted-foreground">{row.fund}</td>
                    <td className="py-1.5 pr-2 text-muted-foreground">{row.macro}</td>
                    <td className="py-1.5 text-muted-foreground">{row.news}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[10px] text-muted-foreground">
            En Supervisado F3 verás el WeightContext real de cada propose (ruleVersion + faltantes).
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Qué se guarda en BD</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2 text-xs">
            {VALUE_ANALYSIS_DB.map((row) => (
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
          <CardTitle className="text-base">Siguiente</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
            {VALUE_ANALYSIS_NEXT.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <HelpSourcesFooter sectionId="value-analysis" />
    </div>
  );
}
