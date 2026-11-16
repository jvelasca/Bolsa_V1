/**
 * Asesor → Laboratorio · salud del laboratorio — slice A3.
 *
 * Fragmento de nivel 3: solo se monta dentro del `TechnicalDetail`
 * (`asesor-lab-metrics-technical`) que abre `lab-summary-panel.tsx`. Por eso su
 * jerga (`campaignId`, cobertura de métricas) no vive en primer nivel.
 *
 * La extracción conserva el marcado uno a uno: mismas cards, mismas rejillas y
 * los mismos rótulos que tenía `research-page.tsx`.
 */

import type { LabHealthDto } from "@bolsa/shared";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
} from "@/components/ui/card";
import { SectionTitle, Stat } from "@/features/research/asesor-ui";

export function LabHealthCard({ health }: { health: LabHealthDto }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <SectionTitle>Salud del laboratorio</SectionTitle>
        <CardDescription>Cobertura de métricas y campañas</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <div className="space-y-3">
          <div className="grid gap-2 sm:grid-cols-3">
            <Stat
              label="Sharpe presente"
              value={`${health.coverage.sharpeRatio.pct.toFixed(1)}%`}
            />
            <Stat
              label="Sortino presente"
              value={`${health.coverage.sortinoRatio.pct.toFixed(1)}%`}
            />
            <Stat
              label="Calmar presente"
              value={`${health.coverage.calmarRatio.pct.toFixed(1)}%`}
            />
          </div>
          <div className="grid gap-2 sm:grid-cols-3">
            <Stat
              label="tradeCount=0"
              value={`${health.zeroTradePct.toFixed(1)}% (${health.zeroTradeCount})`}
            />
            <Stat label="Campañas" value={String(health.campaignCount)} />
            <Stat
              label="Sin experimentos"
              value={`${health.instrumentsWithoutTrials} / ${health.activeInstruments}`}
            />
          </div>
          {health.campaigns.length > 0 && (
            <p className="text-xs text-muted-foreground">
              Campañas más activas:{" "}
              {health.campaigns
                .slice(0, 5)
                .map((c) => `${c.campaignId} (${c.trials})`)
                .join(" · ")}
            </p>
          )}
          <p className="text-xs text-muted-foreground">{health.caveat}</p>
        </div>
      </CardContent>
    </Card>
  );
}
