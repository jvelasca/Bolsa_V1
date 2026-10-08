/**
 * UI Contract 5.0 (`UI5-21`, enmienda UI 7.0) — modo operativo persistente.
 *
 * Chip-**enlace** (Información + Navegación) que informa del modo de operativa vigente
 * (`AUTO`/`SEMI`/`MANUAL`) y da acceso directo al espacio AUTO. Resuelve que AUTO deje de parecer
 * una herramienta administrativa sin promocionarlo a puerta L1.
 *
 * Invariantes:
 * - **No** es una sexta puerta L1 (`UI5-02`): vive FUERA de `nav[aria-label="Principal"]`.
 * - **No** cambia el modo: sólo lo informa y enlaza. El cambio sigue en el libro operativo
 *   (`demo-book-mode-panel`, `UI5-17`).
 *
 * @see docs/engineering/spec-ui-contract-5-0-2026-10-08.md §UI5-21
 * @see docs/adr/040-user-information-architecture.md §13
 */

import { NavLink } from "react-router-dom";
import { Gauge } from "lucide-react";
import { AUTO_ROOT_PATH } from "@/features/auto/auto-nav";
import {
  OPERATION_MODE_LABEL,
  type OperationMode,
} from "@/features/operations/operation-mode";
import { useDemoBookPrefs } from "@/features/trading/use-demo-book-prefs";
import type { DemoBookMode } from "@/features/trading/demo-book-prefs";
import { cn } from "@/lib/utils";

/** Un único casing de modo (`UI5-10`): el libro DEMO se traduce al vocabulario canónico. */
const DEMO_BOOK_TO_OPERATION_MODE: Record<DemoBookMode, OperationMode> = {
  manual: "MANUAL",
  semi: "SEMI",
  auto: "AUTO",
};

export function OperativeModeChip({ className }: { className?: string }) {
  const prefs = useDemoBookPrefs();
  const label = OPERATION_MODE_LABEL[DEMO_BOOK_TO_OPERATION_MODE[prefs.mode]];

  return (
    <NavLink
      to={AUTO_ROOT_PATH}
      data-testid="operative-mode-chip"
      data-mode={label}
      title={`Modo de operativa: ${label}. Abre el espacio AUTO. Es dinero virtual, no real.`}
      aria-label={`Modo de operativa ${label}. Abrir AUTO.`}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-1.5 rounded-md border border-border bg-background/60 px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
          isActive && "border-primary/40 text-primary",
          className,
        )
      }
    >
      <Gauge className="h-3.5 w-3.5 shrink-0" aria-hidden />
      <span className="hidden sm:inline">Operativa ·</span>
      <span className="font-semibold text-foreground">{label}</span>
    </NavLink>
  );
}
