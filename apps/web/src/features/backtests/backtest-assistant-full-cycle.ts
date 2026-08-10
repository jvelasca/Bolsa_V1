/**
 * Ciclo completo del Asistente (1 valor).
 *
 * Flujo: Probar genéricas → Coach (ACK¹) → Lab → Revalidar (ACK final) → Finalistas.
 *
 * Política conservadora (producto):
 * - ACK¹ (si débil/discrepancia y `requireAckBeforeLab`) puerta al Lab.
 * - Atajo opcional `saveSemifinalSkipLab` (OFF): semifinal sin optimizar.
 * - Finalistas `active` si hubo ≥1 Mejor Lab + Coach² `canSaveTop`, **o**
 *   primera escritura (sin TOP durable previo) aunque Lab no mejore.
 * - Sin mejora Lab + TOP durable: **no** Revalidar y **no pisar** TOP previo.
 * - TOP huérfano (slots sin estrategia en BD) ≡ sin TOP → primera escritura.
 *
 * Orquestación UI: `backtests-page.tsx` (`fullCycleActive`, `settleFullCycle`).
 * Lab board: `autoHandoff` → `shouldAutoHandoffLab`.
 * Explore: `autoSaveFinalists` → `resolveFullCycleSaveDecision`.
 *
 * Pref: `AssistantPrefs.fullCycleOnPlay` (default ON). Lista + ciclo = Lista AUTO
 * (`backtest-list-auto.ts`), no este módulo.
 *
 * @see docs/engineering/research-lifecycle.md § Embudo D
 * @see docs/engineering/backtesting-funnel-handoff-2026-07-29.md
 */

/** Dual-audit pide reserva humana (ACK¹ o ACK final). */
export function coachNeedsHumanAck(
  confidence: string | null | undefined,
): boolean {
  return confidence === "weak" || confidence === "discrepancy";
}

/**
 * TOP usable para «conservar previos»: ≥1 slot con `strategyDefinitionId`
 * que aún existe en Biblioteca. Si todos los slots están huérfanos (estrategias
 * borradas sin Eliminar Finalistas), no cuenta como TOP durable.
 */
export function instrumentTopIsDurable(
  top:
    | {
        slots?: Array<{ strategyDefinitionId?: string | null }> | null;
      }
    | null
    | undefined,
  knownStrategyIds: ReadonlySet<string>,
): boolean {
  if (!top?.slots?.length) return false;
  const ids = top.slots
    .map((s) => s.strategyDefinitionId)
    .filter((id): id is string => Boolean(id));
  if (ids.length === 0) return false;
  return ids.some((id) => knownStrategyIds.has(id));
}

export type FullCyclePhase =
  | "idle"
  | "universe"
  | "lab"
  | "coach2"
  | "save_finalists"
  | "done"
  | "aborted";

/** Decisión de auto-guardar Finalistas tras Coach². */
export type FullCycleSaveDecision =
  | { action: "save_active"; reason: string }
  | { action: "skip_keep_previous"; reason: string }
  | { action: "skip_no_candidates"; reason: string };

/**
 * ¿El Lab board puede auto-pasar a Coach²?
 * Requiere ciclo activo, todas las zonas terminadas y ≥1 mejora.
 */
export function shouldAutoHandoffLab(opts: {
  fullCycleActive: boolean;
  allZonesDone: boolean;
  improvedCount: number;
  alreadyTriggered: boolean;
}): boolean {
  if (!opts.fullCycleActive || opts.alreadyTriggered) return false;
  if (!opts.allZonesDone) return false;
  return opts.improvedCount > 0;
}

/**
 * Mensaje de política cuando el Lab terminó sin Mejor ≥ ancla.
 * `null` si aún no hay resultados o sí hubo mejoras.
 */
export function labNoImproveStatus(
  improvedCount: number,
  doneCount: number,
): string | null {
  if (doneCount <= 0) return null;
  if (improvedCount > 0) return null;
  return "Ciclo: Lab sin Mejor ≥ ancla. No se pisan Finalistas active. Revisa zonas o cambia candidatas.";
}

/** Timeout Lab por ticker en ciclo / Lista AUTO (jobs colgados o worker caído). */
export const LAB_CYCLE_WATCHDOG_MS = 8 * 60 * 1000;

/**
 * ¿Una zona Lab ya es terminal (puede cerrar el board)?
 * Evita hang: job fallido, sin enqueue, o resultado listo.
 */
export function isLabZoneTerminal(opts: {
  hasSeed: boolean;
  hasJob: boolean;
  hasResult: boolean;
  activityPhase?: string | null;
}): boolean {
  if (!opts.hasSeed) return false;
  if (opts.hasResult) return true;
  const phase = opts.activityPhase ?? null;
  if (phase === "failed" || phase === "completed") return true;
  // Semilla sin job encolado → no hay nada que esperar.
  if (!opts.hasJob) return true;
  return false;
}

export function labEmptyZonesStatus(): string {
  return "Ciclo: Lab sin zonas optimizables. No se pisan Finalistas active.";
}

export function labWatchdogStatus(): string {
  return "Ciclo: Lab timeout · no se pisan Finalistas. Siguiente valor…";
}

export function universeEmptyStatus(detail?: string | null): string {
  const d = detail?.trim();
  return d
    ? `Ciclo: Universo sin TOP útil (${d}). No se pisan Finalistas.`
    : "Ciclo: Universo sin TOP útil. No se pisan Finalistas.";
}

/**
 * Tras Coach² (`post_lab`):
 * - Con mejora Lab + TOP guardable → save_active
 * - Sin mejora Lab + TOP durable en BD → skip_keep_previous
 * - Sin mejora Lab + sin TOP (o TOP huérfano) → save_active (primera escritura)
 * - Sin candidatas / ACK → skip_no_candidates
 *
 * `hasExistingTop` debe ser false si el TOP solo referencia estrategias borradas.
 */
export function resolveFullCycleSaveDecision(opts: {
  postLab: boolean;
  labImprovedCount: number;
  canSaveTop: boolean;
  existingTopStatus?: string | null;
  /** TOP durable (slots con estrategia aún en BD). Huérfano ≡ false. */
  hasExistingTop?: boolean;
}): FullCycleSaveDecision {
  if (!opts.postLab) {
    return {
      action: "skip_no_candidates",
      reason: "Solo se auto-guardan Finalistas tras Coach² (post-Lab).",
    };
  }

  const hasTop =
    opts.hasExistingTop !== undefined
      ? opts.hasExistingTop
      : opts.existingTopStatus === "active" ||
        opts.existingTopStatus === "semifinal";

  if (opts.labImprovedCount <= 0) {
    if (hasTop) {
      return {
        action: "skip_keep_previous",
        reason:
          opts.existingTopStatus === "active"
            ? "Sin mejora Lab: se conserva el TOP active previo."
            : "Sin mejora Lab: se conserva el TOP semifinal previo.",
      };
    }
    if (!opts.canSaveTop) {
      return {
        action: "skip_no_candidates",
        reason:
          "Sin TOP previo ni candidatas Coach² guardables. No se escribe Finalistas.",
      };
    }
    return {
      action: "save_active",
      reason:
        "Sin TOP previo · Coach OK → Finalistas lab_validated (primera escritura).",
    };
  }

  if (!opts.canSaveTop) {
    return {
      action: "skip_no_candidates",
      reason:
        "Coach² sin TOP guardable (ack / quorum / runId). No se escribe Finalistas.",
    };
  }
  return {
    action: "save_active",
    reason: "Mejor(es) Lab + Coach² OK → Finalistas lab_validated.",
  };
}

/**
 * ¿El auto-save de Finalistas debe esperar (no skip) en este frame?
 * Evita la carrera ACS: running acaba y deepNote aún vacío.
 */
export function shouldWaitBeforeFinalistsAutoSave(opts: {
  running: boolean;
  okCount: number;
  recommendationCount: number;
  postLabRecsWithRunId: number;
  postLab: boolean;
}): boolean {
  if (opts.running) return true;
  if (opts.okCount > 0 && opts.recommendationCount === 0) return true;
  if (
    opts.postLab &&
    opts.recommendationCount > 0 &&
    opts.postLabRecsWithRunId === 0
  ) {
    return true;
  }
  return false;
}

/** Título del botón Play según pref de ciclo (1 valor). */
export function fullCyclePlayTitle(fullCycleOnPlay: boolean): string {
  return fullCycleOnPlay
    ? "Play: ciclo (Probar genéricas → Coach → Lab → Revalidar → Finalistas)"
    : "Play: ejecutar siguiente paso";
}
