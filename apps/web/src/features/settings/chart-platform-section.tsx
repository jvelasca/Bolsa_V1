import { Link } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { SettingsSection } from "@/features/settings/settings-section";
import {
  CHART_CAPABILITIES,
  CHART_STATUS_LABEL,
  CHART_TRACKER_SYNC,
  type ChartTrackStatus,
} from "@/features/settings/chart-platform-tracker";

const STATUS_CLASS: Record<ChartTrackStatus, string> = {
  done: "border-emerald-500/40 bg-emerald-500/10 text-emerald-400",
  partial: "border-amber-500/40 bg-amber-500/10 text-amber-400",
  planned: "border-border bg-muted/30 text-muted-foreground",
};

export function ChartPlatformSection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const body = (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Dónde se configura cada cosa</CardTitle>
          <CardDescription>
            Resumen de estado (Ayuda). No es un backlog editable. Sync{" "}
            {CHART_TRACKER_SYNC.asOf}.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 text-sm md:grid-cols-2">
          <div className="rounded-md border border-border bg-muted/20 p-3">
            <p className="font-medium">Configuración (ajustes)</p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-muted-foreground">
              <li>
                <span className="text-foreground">General</span> — cuenta
                activa, workspace, plantilla de gráficos nuevos
              </li>
              <li>
                <span className="text-foreground">Otras</span> — sync automática
                Yahoo y estado de proveedores
              </li>
              <li>
                Comisiones, confirmaciones; notificaciones / sonidos / atajos
                (pendientes)
              </li>
            </ul>
          </div>
          <div className="rounded-md border border-primary/30 bg-primary/5 p-3">
            <p className="font-medium">Por gráfico / instrumento</p>
            <ul className="mt-2 list-inside list-disc space-y-1 text-muted-foreground">
              <li>Timeframe, zoom e indicadores de la pestaña activa</li>
              <li>Objetos gráficos, plantillas e inspector</li>
              <li>
                <Link to="/trading" className="text-primary hover:underline">
                  Trading → barras del gráfico y menú Indicadores
                </Link>
              </li>
            </ul>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Estado de la plataforma gráfica</CardTitle>
          <CardDescription>
            Datos en <code className="text-xs">chart-platform-tracker.ts</code>{" "}
            · alineado con{" "}
            <code className="text-xs">{CHART_TRACKER_SYNC.adr}</code>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {CHART_CAPABILITIES.map((item) => (
            <div
              key={item.id}
              className="flex flex-col gap-1 rounded-md border border-border/70 px-3 py-2 sm:flex-row sm:items-start sm:justify-between sm:gap-3"
            >
              <div className="min-w-0">
                <p className="text-sm font-medium">{item.title}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {item.detail}
                </p>
              </div>
              <span
                className={cn(
                  "shrink-0 self-start rounded border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide",
                  STATUS_CLASS[item.status],
                )}
              >
                {CHART_STATUS_LABEL[item.status]}
              </span>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Documentación</CardTitle>
          <CardDescription>
            Diseño de referencia — no usar fases antiguas del ADR como backlog
          </CardDescription>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          <p>
            Diseño en <code className="text-xs">{CHART_TRACKER_SYNC.adr}</code>.
            Detalle de barras:{" "}
            <code className="text-xs">{CHART_TRACKER_SYNC.chartDataBar}</code>.
            Este resumen en Ayuda es la fuente de verdad del estado actual en la
            app.
          </p>
        </CardContent>
      </Card>
    </>
  );

  if (compact) {
    return <div className="space-y-4">{body}</div>;
  }

  return (
    <SettingsSection
      id="chart-platform"
      title="Plataforma gráfica"
      description="Estado real del entorno de análisis — alimentado por chart-platform-tracker."
    >
      {body}
    </SettingsSection>
  );
}
