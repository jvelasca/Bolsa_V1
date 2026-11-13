/**
 * F8 — derive PAPER AUTO / SEMI posture from demo-book prefs + arm + kill-switch env.
 */

import { buildPaperAutoPosture, type PaperAutoPostureV1 } from "@bolsa/shared";
import { loadAutoArm } from "@/features/trading/demo-book-auto-arm";
import {
  loadDemoBookPrefs,
  type DemoBookMode,
} from "@/features/trading/demo-book-prefs";

export function resolvePaperAutoPosture(input?: {
  bookMode?: DemoBookMode | null;
  autoArmed?: boolean | null;
  paperDExecuteEnv?: boolean | null;
}): PaperAutoPostureV1 {
  // Con `autoArmed`/`bookMode` explícitos (hook reactivo) NO se relee localStorage: la
  // lectura imperativa congelaría el valor y divergiría del estado real.
  const bookMode = input?.bookMode ?? loadDemoBookPrefs().mode;
  const autoArmed = input?.autoArmed ?? loadAutoArm().armed;
  return buildPaperAutoPosture({
    bookMode,
    autoArmed,
    paperDExecuteEnv: input?.paperDExecuteEnv ?? false,
  });
}
