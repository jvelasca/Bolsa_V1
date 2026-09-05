/**
 * V1.42 F8 — PAPER AUTO posture (product honesty).
 * Same spine as SEMI; AUTO omits human Confirm. Arm ≠ execute.
 * V2.43 — operator cabin labels: ARM ≠ autorización de operación.
 * V2.46 — arm chrome from autoActive (mode=auto ∧ armed). MANUAL/SEMI never AUTO ARMADO.
 * LIVE broker / thaw estricto / PAPER_D_EXECUTE default-on: out of scope.
 *
 * @see docs/engineering/spec-v142-operating-excellence-2026-08-31.md §D F8
 * @see docs/adr/042-operating-excellence.md
 * @see docs/engineering/traspaso-relevo-v2-8-operator-certification-2026-09-05.md
 */

export type PaperBookModeV1 = "manual" | "semi" | "auto";

/** V2.43 — inequívoco en cabina: DESARMADO | ARMADO. */
export type PaperAutoArmStateLabelV1 = "AUTO DESARMADO" | "AUTO ARMADO";

export type PaperAutoPostureV1 = {
  bookMode: PaperBookModeV1;
  /** Local A3 arm (`ACTIVAR AUTO`). */
  autoArmed: boolean;
  /** Server eco `PAPER_D_EXECUTE` (opt-in; default off). */
  paperDExecuteEnv: boolean;
  /** True when mode=auto and arm completed. */
  autoActive: boolean;
  modeLabel: string;
  modeDetail: string;
  /**
   * Short surface badge when AUTO active.
   * e.g. «AUTO armado · ejecución off» when env off.
   */
  statusBadge: string | null;
  /** SEMI: true. AUTO active: false (omit firma). MANUAL: false. */
  requiresHumanConfirm: boolean;
  /**
   * AUTO active + PAPER_D_EXECUTE on → paper_auto Router may fill.
   * Never true for SEMI (Confirm is the firma).
   */
  executeEligible: boolean;
  /** One-line spine for tooltips / footers. */
  spineLine: string;
  /**
   * V2.43 / V2.46 — chrome ESTADO.
   * Derived from autoActive (AUTO mode ∧ armed), not the raw latch.
   */
  armStateLabel: PaperAutoArmStateLabelV1;
  /** V2.43 — chrome RESULTADO / venue (siempre PAPER en BETA). */
  executionVenueLabel: string;
  /**
   * V2.43 — Arm = permiso de motor · no autoriza una operación.
   * Never contains «operación autorizada».
   */
  armPermissionLine: string;
};

export const PAPER_AUTO_ARMED_EXEC_OFF = "AUTO armado · ejecución off";
export const PAPER_AUTO_ARMED_EXEC_ON = "AUTO armado · ejecución on";

export const PAPER_SEMI_SPINE =
  "IA → Risk → Policy → Humano confirma → Execution";
export const PAPER_AUTO_SPINE = "IA → Risk → Policy → Execution";

/** V2.43 — ESTADO chrome. */
export const PAPER_AUTO_ARM_STATE_DISARMED: PaperAutoArmStateLabelV1 =
  "AUTO DESARMADO";
export const PAPER_AUTO_ARM_STATE_ARMED: PaperAutoArmStateLabelV1 =
  "AUTO ARMADO";

/** V2.43 — venue honesty (BETA = PAPER). */
export const PAPER_AUTO_EXECUTION_VENUE = "EJECUCIÓN: PAPER";

/**
 * V2.43 — Arm ≠ autorización de operación concreta.
 * Confirm = firma. Never claim «operación autorizada».
 */
export const PAPER_AUTO_ARM_PERMISSION_LINE =
  "Arm = permiso de motor · no autoriza una operación · Confirm = firma";

function cabinArmLabels(
  autoActive: boolean,
): Pick<
  PaperAutoPostureV1,
  "armStateLabel" | "executionVenueLabel" | "armPermissionLine"
> {
  return {
    armStateLabel: autoActive
      ? PAPER_AUTO_ARM_STATE_ARMED
      : PAPER_AUTO_ARM_STATE_DISARMED,
    executionVenueLabel: PAPER_AUTO_EXECUTION_VENUE,
    armPermissionLine: PAPER_AUTO_ARM_PERMISSION_LINE,
  };
}

export function buildPaperAutoPosture(input: {
  bookMode?: PaperBookModeV1 | null;
  autoArmed?: boolean | null;
  paperDExecuteEnv?: boolean | null;
}): PaperAutoPostureV1 {
  const bookMode: PaperBookModeV1 =
    input.bookMode === "manual" ||
    input.bookMode === "semi" ||
    input.bookMode === "auto"
      ? input.bookMode
      : "semi";
  const autoArmed = input.autoArmed === true;
  const paperDExecuteEnv = input.paperDExecuteEnv === true;
  const autoActive = bookMode === "auto" && autoArmed;
  const armChrome = cabinArmLabels(autoActive);

  if (bookMode === "manual") {
    return {
      bookMode,
      autoArmed,
      paperDExecuteEnv,
      autoActive: false,
      modeLabel: "MANUAL",
      modeDetail: "Aviso · sin cola Confirm · sin AUTO",
      statusBadge: null,
      requiresHumanConfirm: false,
      executeEligible: false,
      spineLine: "MANUAL · humano opera · sin AUTO",
      ...armChrome,
    };
  }

  if (autoActive) {
    const executeEligible = paperDExecuteEnv;
    return {
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv,
      autoActive: true,
      modeLabel: "AUTO",
      modeDetail: executeEligible
        ? `${PAPER_AUTO_SPINE} · paper · arm ≠ LIVE`
        : `${PAPER_AUTO_ARMED_EXEC_OFF} · arm ≠ execute · PAPER_D_EXECUTE opt-in`,
      statusBadge: executeEligible
        ? PAPER_AUTO_ARMED_EXEC_ON
        : PAPER_AUTO_ARMED_EXEC_OFF,
      requiresHumanConfirm: false,
      executeEligible,
      spineLine: PAPER_AUTO_SPINE,
      ...armChrome,
    };
  }

  // SEMI default (also auto without arm — prefs coerce to semi in UI).
  return {
    bookMode: bookMode === "auto" ? "semi" : bookMode,
    autoArmed,
    paperDExecuteEnv,
    autoActive: false,
    modeLabel: "SEMI",
    modeDetail: `${PAPER_SEMI_SPINE} · AUTO off`,
    statusBadge: null,
    requiresHumanConfirm: true,
    executeEligible: false,
    spineLine: PAPER_SEMI_SPINE,
    ...armChrome,
  };
}
