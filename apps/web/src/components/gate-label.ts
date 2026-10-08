/**
 * UI 6.x (`R-G1`/`RT-02`) — traducción de la decisión diaria a lenguaje de usuario.
 *
 * El permiso diario se cuenta en lenguaje de resultado: el literal «Gate» + su valor crudo
 * (`PASS`/`VETO`/`DEFERRED`) no se muestran en primer nivel. Fuente única para las
 * superficies que hoy/señales repiten el rótulo.
 *
 * @see docs/engineering/auditoria-ui-6-x-global-2026-10-08.md §4 (H-03)
 * @see apps/web/src/components/first-level-gate.ts
 */

import { absentDataLabel } from "@/components/absent-data";

/** Rótulo humano de un gate de permiso diario. Ausencia → `Sin dato todavía`. */
export function gateHumanLabel(gate: string | null | undefined): string {
  switch (gate?.toUpperCase()) {
    case "PASS":
      return "Sin bloqueos";
    case "VETO":
      return "Bloqueado";
    case "DEFERRED":
      return "Aplazado";
    default:
      return absentDataLabel();
  }
}
