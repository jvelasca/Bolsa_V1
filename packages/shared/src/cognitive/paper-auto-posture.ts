/**
 * V1.42 F8 — PAPER AUTO posture (product honesty).
 * Same spine as SEMI; AUTO omits human Confirm. Arm ≠ execute.
 * LIVE broker / thaw estricto / PAPER_D_EXECUTE default-on: out of scope.
 *
 * @see docs/engineering/spec-v142-operating-excellence-2026-08-31.md §D F8
 * @see docs/adr/042-operating-excellence.md
 */

export type PaperBookModeV1 = "manual" | "semi" | "auto";

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
};

export const PAPER_AUTO_ARMED_EXEC_OFF = "AUTO armado · ejecución off";
export const PAPER_AUTO_ARMED_EXEC_ON = "AUTO armado · ejecución on";

export const PAPER_SEMI_SPINE =
  "IA → Risk → Policy → Humano confirma → Execution";
export const PAPER_AUTO_SPINE = "IA → Risk → Policy → Execution";

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
  };
}
