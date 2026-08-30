/**
 * Lista de atajos V1.31 — SoT para Config → Atajos y tests.
 * Las rutas destino viven en daily-nav / confirm-nav / command-registry.
 */
import {
  ASESOR_LABEL,
  CARTERA_LABEL,
  CONFIRMAR_LABEL,
  LABORATORIO_LABEL,
  MERCADO_LABEL,
  MESA_LABEL,
} from "@/features/confirm/daily-nav";

export type PlatformShortcutRow = {
  id: string;
  keys: string;
  action: string;
};

export const PLATFORM_SHORTCUTS: PlatformShortcutRow[] = [
  {
    id: "palette",
    keys: "Ctrl/⌘ K",
    action: "Abrir command palette",
  },
  {
    id: "hoy",
    keys: "Alt+1",
    action: `Ir a ${MESA_LABEL}`,
  },
  {
    id: "mercado",
    keys: "Alt+2",
    action: `Ir a ${MERCADO_LABEL}`,
  },
  {
    id: "cartera",
    keys: "Alt+3",
    action: `Ir a ${CARTERA_LABEL}`,
  },
  {
    id: "asesor",
    keys: "Alt+4",
    action: `Ir a ${ASESOR_LABEL}`,
  },
  {
    id: "laboratorio",
    keys: "Alt+5",
    action: `Ir a ${LABORATORIO_LABEL}`,
  },
  {
    id: "confirmar",
    keys: "Alt+C",
    action: `Ir a ${CONFIRMAR_LABEL}`,
  },
];
