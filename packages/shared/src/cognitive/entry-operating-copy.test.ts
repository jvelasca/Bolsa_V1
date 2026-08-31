import { describe, expect, it } from "vitest";
import {
  entryOperatingCtaFromPhase,
  formatEntryOperatingPhrase,
} from "./entry-operating-copy.js";
import { buildPaperAutoPosture } from "./paper-auto-posture.js";

describe("entry-operating-copy PAPER AUTO (F8)", () => {
  it("SEMI disparada still requires Confirm CTA", () => {
    const cta = entryOperatingCtaFromPhase("disparada");
    expect(cta.kind).toBe("review_confirm");
    expect(cta.label).toBe("Revisar y confirmar");
    expect(formatEntryOperatingPhrase("disparada")).toMatch(/Confirm/);
  });

  it("AUTO armed + env off omits Confirm CTA and says ejecución off", () => {
    const paperAuto = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: false,
    });
    const cta = entryOperatingCtaFromPhase("disparada", { paperAuto });
    expect(cta.kind).toBe("none");
    expect(cta.label).toMatch(/ejecución off/);
    expect(formatEntryOperatingPhrase("disparada", { paperAuto })).toMatch(
      /arm ≠ execute|ejecución off/i,
    );
    expect(formatEntryOperatingPhrase("disparada", { paperAuto })).not.toMatch(
      /firma en Confirm/,
    );
  });

  it("AUTO armed + env on omits Confirm; same spine without firma", () => {
    const paperAuto = buildPaperAutoPosture({
      bookMode: "auto",
      autoArmed: true,
      paperDExecuteEnv: true,
    });
    const cta = entryOperatingCtaFromPhase("propuesta", { paperAuto });
    expect(cta.kind).toBe("none");
    expect(cta.label).toMatch(/ejecución on/);
    expect(formatEntryOperatingPhrase("propuesta", { paperAuto })).toMatch(
      /sin cola Confirm|PAPER AUTO/i,
    );
  });
});
