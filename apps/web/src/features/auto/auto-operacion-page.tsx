/**
 * AUTO · OPERACIÓN canónica `/auto/operar/operacion/:cycleId` (ADR-044).
 *
 * Lectura causal de UNA operación: qué pasó → por qué → qué riesgo tenía → qué
 * qué precio se aplicó → qué resultado → qué enseña DÍA-D. La selección viaja en la
 * URL (ruta); cambiar de ciclo navega a la operación correspondiente.
 */

import { Link, useNavigate, useParams } from "react-router-dom";
import {
  AutoSectionBlockHeading,
  AutoSectionHeading,
} from "@/components/layout/auto-workspace-layout";
import { AutoOperationStoryPanel } from "@/features/auto-monitor/auto-operation-story-panel";
import { useAutoOperationalMonitor } from "@/features/auto-monitor/use-auto-operational-monitor";
import { AUTO_OPERAR_PATH, autoOperacionHref } from "@/features/auto/auto-nav";
import { buildAutoOperationSheet } from "@/features/auto/auto-operation-sheet";
import { AutoOperationSheetView } from "@/features/auto/auto-operation-sheet-view";

export function AutoOperacionPage() {
  const { cycleId } = useParams<{ cycleId: string }>();
  const navigate = useNavigate();
  const { view } = useAutoOperationalMonitor();
  const cycle = view?.cycles.find((item) => item.cycleId === cycleId) ?? null;
  const title = cycle?.instrumentId ?? cycleId ?? "Operación";

  return (
    <div className="space-y-6" data-testid="auto-operacion-page">
      <div className="space-y-2">
        <Link
          to={AUTO_OPERAR_PATH}
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-primary"
        >
          ← Operar
        </Link>
        <AutoSectionHeading
          title={`Operación · ${title}`}
          description="Qué pasó → por qué → qué riesgo tenía → qué precio se aplicó → qué resultado → qué enseña DÍA-D."
        />
      </div>

      <section
        className="space-y-2"
        aria-labelledby="auto-operacion-sheet-heading"
      >
        <AutoSectionBlockHeading id="auto-operacion-sheet-heading">
          Ficha de la operación
        </AutoSectionBlockHeading>
        {cycle ? (
          <AutoOperationSheetView sheet={buildAutoOperationSheet(cycle)} />
        ) : (
          <p
            className="text-sm text-muted-foreground"
            data-testid="auto-operacion-sheet-hole"
          >
            Sin dato todavía: no hay una operación con ese identificador.
          </p>
        )}
      </section>

      <section
        className="space-y-2"
        aria-labelledby="auto-operacion-story-heading"
      >
        <AutoSectionBlockHeading id="auto-operacion-story-heading">
          Historia
        </AutoSectionBlockHeading>
        <AutoOperationStoryPanel
          cycleIdOverride={cycleId ?? null}
          onSelectCycle={(id) => navigate(autoOperacionHref(id))}
        />
      </section>
    </div>
  );
}
