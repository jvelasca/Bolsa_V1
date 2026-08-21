/**
 * Tests — CTA del diálogo IA (firma → Confirmar; resto → Ayuda).
 */

import { describe, expect, it } from "vitest";
import { AI_INFO_SURFACES } from "@/features/ai/ai-info-catalog";
import {
  AI_INFO_HELP_CTA_AYUDA,
  aiInfoHelpCtaLabel,
} from "@/features/ai/ai-info-button-copy";
import { CONFIRMAR_LABEL } from "@/features/confirm/daily-nav";

describe("aiInfoHelpCtaLabel", () => {
  it("labels supervised-f3 as Confirmar", () => {
    expect(aiInfoHelpCtaLabel("supervised-f3")).toBe(
      `Abrir ${CONFIRMAR_LABEL}`,
    );
    expect(AI_INFO_SURFACES.chart_propose.helpPanel).toBe("supervised-f3");
    expect(aiInfoHelpCtaLabel(AI_INFO_SURFACES.chart_propose.helpPanel)).toBe(
      `Abrir ${CONFIRMAR_LABEL}`,
    );
  });

  it("keeps Ayuda when there is no F3 panel", () => {
    expect(aiInfoHelpCtaLabel(undefined)).toBe(AI_INFO_HELP_CTA_AYUDA);
    expect(aiInfoHelpCtaLabel(null)).toBe(AI_INFO_HELP_CTA_AYUDA);
    expect(AI_INFO_SURFACES.fa_copilot.helpPanel).toBeUndefined();
    expect(aiInfoHelpCtaLabel(AI_INFO_SURFACES.fa_copilot.helpPanel)).toBe(
      AI_INFO_HELP_CTA_AYUDA,
    );
  });
});
