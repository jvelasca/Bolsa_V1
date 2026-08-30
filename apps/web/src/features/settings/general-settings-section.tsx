/**
 * Configuración → General: preferencias del espacio activo + plantilla de gráficos nuevos.
 * El gestor completo (nuevo / duplicar / renombrar) se abre con «Gestionar espacios…».
 *
 * @see docs/WORKSPACE_PERSISTENCE.md
 */
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { checkboxClassName } from "@/components/ui/dialog";
import { useUiStore } from "@/stores/ui-store";
import { useTradingLayoutStore } from "@/stores/trading-layout-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { SettingsSection } from "@/features/settings/settings-section";
import { ChartNewChartTemplatePinButton } from "@/features/charts/chart-new-chart-template-pin-button";
import type { UiTheme } from "@/features/command-palette/ui-theme";
import {
  NAMED_LAYOUT_LABELS,
  type NamedLayoutId,
} from "@/features/command-palette/named-layout";

export function GeneralSettingsSection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const workspace = useWorkspaceStore((s) => s.workspace);
  const setAutoSave = useWorkspaceStore((s) => s.setAutoSave);
  const setOpenOnStartup = useWorkspaceStore((s) => s.setOpenOnStartup);
  const openWorkspacePicker = useUiStore((s) => s.openWorkspacePicker);
  const uiDensity = useUiStore((s) => s.uiDensity);
  const setUiDensity = useUiStore((s) => s.setUiDensity);
  const uiTheme = useUiStore((s) => s.uiTheme);
  const setUiTheme = useUiStore((s) => s.setUiTheme);
  const namedLayoutId = useTradingLayoutStore((s) => s.namedLayoutId);
  const applyNamedLayout = useTradingLayoutStore((s) => s.applyNamedLayout);
  const resetLayout = useTradingLayoutStore((s) => s.resetLayout);

  const body = (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Espacio de trabajo</CardTitle>
          <CardDescription>
            Activo:{" "}
            <span className="font-medium text-foreground">
              {workspace.name}
            </span>
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className={checkboxClassName}
              checked={workspace.preferences.autoSave}
              onChange={(e) => setAutoSave(e.target.checked)}
            />
            Autoguardado en servidor al cambiar layout o gráficos
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className={checkboxClassName}
              checked={workspace.preferences.openOnStartup}
              onChange={(e) => setOpenOnStartup(e.target.checked)}
            />
            Preferido al arrancar (si no hay último activo en este dispositivo)
          </label>
          <p className="text-[11px] text-muted-foreground">
            Al abrir la app se restaura el espacio activo guardado localmente;
            este flag solo actúa como reserva (estrella en el gestor).
          </p>
          <button
            type="button"
            className="rounded-md border border-border px-3 py-1.5 hover:bg-accent"
            onClick={openWorkspacePicker}
          >
            Gestionar espacios…
          </button>
          <div className="space-y-2 border-t border-border pt-4">
            <p className="text-xs font-medium text-foreground">
              Plantilla para gráficos nuevos
            </p>
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              Activa el icono de plantilla en el gráfico que quieras usar como
              referencia. Los valores que abras después copiarán su
              configuración en vivo (indicadores, barra, estilo). Desactívalo
              para volver a los defaults del workspace.
            </p>
            <ChartNewChartTemplatePinButton />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Interfaz</CardTitle>
          <CardDescription>
            Paneles de Trading y opciones visuales
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <label className="flex flex-col gap-1.5 text-foreground">
            <span className="font-medium">Tema</span>
            <select
              value={uiTheme}
              onChange={(e) => setUiTheme(e.target.value as UiTheme)}
              className="max-w-xs rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="dark">Oscuro</option>
              <option value="light">Claro</option>
              <option value="system">Sistema</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-foreground">
            <span className="font-medium">Densidad de UI</span>
            <select
              value={uiDensity}
              onChange={(e) =>
                setUiDensity(e.target.value as "comfortable" | "compact")
              }
              className="max-w-xs rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              <option value="comfortable">Comfortable</option>
              <option value="compact">Compact</option>
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-foreground">
            <span className="font-medium">Layout Mercado</span>
            <select
              value={namedLayoutId ?? ""}
              onChange={(e) => {
                const v = e.target.value;
                if (v === "simple" || v === "trader" || v === "analista") {
                  applyNamedLayout(v satisfies NamedLayoutId);
                }
              }}
              className="max-w-xs rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {namedLayoutId == null ? (
                <option value="" disabled>
                  Personalizado
                </option>
              ) : null}
              {(Object.keys(NAMED_LAYOUT_LABELS) as NamedLayoutId[]).map(
                (id) => (
                  <option key={id} value={id}>
                    {NAMED_LAYOUT_LABELS[id]}
                  </option>
                ),
              )}
            </select>
          </label>
          <p>
            El layout de paneles (watchlist / operaciones) y los anchos de
            columnas de Listas/Valores se guardan en este dispositivo:
            escritorio y portátil no se pisan. También puedes restablecer los
            paneles desde la barra superior (Trading).
          </p>
          <button
            type="button"
            className="rounded-md border border-border px-3 py-1.5 text-foreground hover:bg-accent"
            onClick={resetLayout}
          >
            Restablecer paneles Trading
          </button>
        </CardContent>
      </Card>
    </>
  );

  if (compact) {
    return <div className="space-y-4">{body}</div>;
  }

  return (
    <SettingsSection
      id="general"
      title="General"
      description="Preferencias del espacio de trabajo y comportamiento de la aplicación."
    >
      {body}
    </SettingsSection>
  );
}
