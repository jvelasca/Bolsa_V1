/**
 * Configuración → General.
 *
 * Tres bloques por ámbito, para que el usuario sepa qué se guarda dónde:
 * - Apariencia: preferencias de la app en **este dispositivo** (`localStorage`).
 * - Mercado: idem (HUD del estado operativo).
 * - Espacio de trabajo: **resumen de solo lectura**; editar se hace en el gestor
 *   (chip superior / botón «Gestionar espacios…»).
 *
 * El diseño de Mercado y «Restablecer paneles» viven en el gestor de espacios:
 * son chrome del espacio, aunque sea por dispositivo.
 *
 * @see docs/WORKSPACE_PERSISTENCE.md
 * @see docs/UI_PREFS_LOCALSTORAGE.md
 */
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { absentDataLabel } from "@/components/absent-data";
import { formatDate } from "@/lib/format";
import { useUiStore } from "@/stores/ui-store";
import { useWorkspaceStore } from "@/stores/workspace-store";
import { SettingsSection } from "@/features/settings/settings-section";
import type { UiTheme } from "@/features/command-palette/ui-theme";
import { DecisionSurfacePlacementToggle } from "@/features/trading/decision-surface-placement-toggle";
import { useMercadoDecisionSurfacePrefs } from "@/features/trading/use-mercado-decision-surface-prefs";

const selectClassName =
  "max-w-xs rounded-md border border-border bg-background px-3 py-2 text-sm";

export function GeneralSettingsSection({
  compact = false,
}: {
  compact?: boolean;
}) {
  const workspace = useWorkspaceStore((s) => s.workspace);
  const activeWorkspaceId = useWorkspaceStore((s) => s.activeWorkspaceId);
  const summaries = useWorkspaceStore((s) => s.workspaceSummaries);
  const openWorkspacePicker = useUiStore((s) => s.openWorkspacePicker);
  const uiDensity = useUiStore((s) => s.uiDensity);
  const setUiDensity = useUiStore((s) => s.setUiDensity);
  const uiTheme = useUiStore((s) => s.uiTheme);
  const setUiTheme = useUiStore((s) => s.setUiTheme);
  const { placement: decisionSurfacePlacement } =
    useMercadoDecisionSurfacePrefs();

  const isPreferred =
    summaries.find((item) => item.id === activeWorkspaceId)?.isDefault ?? false;
  const openCharts = workspace.charts.filter((tab) => tab.instrumentId).length;
  const listNames = (workspace.list.carouselListIds ?? []).length;

  const body = (
    <>
      <Card>
        <CardHeader>
          <CardTitle>Apariencia</CardTitle>
          <CardDescription>
            Solo este dispositivo: escritorio y portátil pueden tener temas
            distintos.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <label className="flex flex-col gap-1.5 text-foreground">
            <span className="font-medium">Tema</span>
            <select
              value={uiTheme}
              onChange={(e) => setUiTheme(e.target.value as UiTheme)}
              className={selectClassName}
            >
              <option value="dark">Oscuro</option>
              <option value="light">Claro</option>
              <option value="system">Sistema</option>
            </select>
            <span className="text-[11px]">
              «Sistema» sigue la preferencia del sistema operativo.
            </span>
          </label>
          <label className="flex flex-col gap-1.5 text-foreground">
            <span className="font-medium">Densidad de UI</span>
            <select
              value={uiDensity}
              onChange={(e) =>
                setUiDensity(e.target.value as "comfortable" | "compact")
              }
              className={selectClassName}
            >
              <option value="comfortable">Cómoda</option>
              <option value="compact">Compacta</option>
            </select>
            <span className="text-[11px]">
              Ajusta el espaciado de tablas, barras y paneles.
            </span>
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Mercado</CardTitle>
          <CardDescription>
            Superficie de decisión (entrada / posición) en el panel DECISIÓN o
            como HUD compacto en el gráfico activo. Solo este dispositivo.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <div className="flex flex-col gap-2 text-foreground">
            <span className="font-medium">Ubicación del estado operativo</span>
            <DecisionSurfacePlacementToggle size="md" />
            <p className="text-[11px] leading-relaxed">
              {decisionSurfacePlacement === "panel"
                ? "El estado completo se muestra en el panel DECISIÓN. El gráfico mantiene las líneas operativas."
                : "El estado compacto flota en el gráfico. El panel DECISIÓN muestra un aviso y la ACCIÓN sigue ahí."}
            </p>
          </div>
        </CardContent>
      </Card>

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
        <CardContent className="space-y-3 text-sm">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-xs">
            <dt className="text-muted-foreground">Gráficos abiertos</dt>
            <dd className="text-foreground">
              {openCharts === 0 ? "Ninguno" : String(openCharts)}
            </dd>
            <dt className="text-muted-foreground">Listas en el carrusel</dt>
            <dd className="text-foreground">
              {listNames === 0 ? "Ninguna" : String(listNames)}
            </dd>
            <dt className="text-muted-foreground">Autoguardado</dt>
            <dd className="text-foreground">
              {workspace.preferences.autoSave ? "Activado" : "Desactivado"}
            </dd>
            <dt className="text-muted-foreground">Preferido al arrancar</dt>
            <dd className="text-foreground">
              {isPreferred ? "Sí (reserva)" : "No"}
            </dd>
            <dt className="text-muted-foreground">Última modificación</dt>
            <dd className="text-foreground">
              {workspace.updatedAt
                ? formatDate(workspace.updatedAt)
                : absentDataLabel()}
            </dd>
          </dl>
          <p className="text-[11px] leading-relaxed text-muted-foreground">
            Los gráficos, listas, dibujos y estas preferencias se guardan en el
            servidor; el diseño de paneles y los anchos de columna, solo en este
            dispositivo. Al abrir la app se restaura el último espacio activo
            local.
          </p>
          <button
            type="button"
            className="rounded-md border border-border px-3 py-1.5 text-foreground hover:bg-accent"
            onClick={openWorkspacePicker}
          >
            Gestionar espacios…
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
      description="Apariencia del dispositivo y resumen del espacio de trabajo activo."
    >
      {body}
    </SettingsSection>
  );
}
